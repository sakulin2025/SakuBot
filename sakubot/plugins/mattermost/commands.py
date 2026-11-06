"""Own Slash commands as durable remote resources, keeping credentials private.

The journal is written before remote mutations. Repair reads the remote state;
it never blindly repeats a command creation or token rotation after a timeout.
"""

import asyncio
import hashlib
import json
import re
import time
import uuid

import httpx
import jsonschema

from sakubot.plugin import object_schema, text

TRIGGER = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
REMOTE_ID = re.compile(r'^[a-z0-9]{26}$')
PUBLIC_FIELDS = ('id', 'command_id', 'team_id', 'trigger', 'display_name', 'description',
                 'hint', 'script_id', 'params', 'user_id', 'channel_id', 'enabled',
                 'callback_url', 'status', 'error', 'updated', 'synced_at')


def redact(value):
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()
                if key not in ('token', 'access_token', 'client_secret')}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class CommandAPIError(RuntimeError):
    def __init__(self, status):
        self.status = status
        reason = {403: '当前账号没有团队的指令管理权限', 401: '账号认证失败',
                  404: '远端指令不存在', 501: '服务器未启用自定义指令'}.get(status, '远端操作失败')
        super().__init__(f'{reason}（HTTP {status}）')


class Commands:
    def __init__(self, plugin):
        self.plugin = plugin
        self.lock = asyncio.Lock()

    def register(self):
        self.plugin.tool('mattermost_command',
            '管理由 SakuBot 创建的 Mattermost Slash 指令。save 创建或修改并自动登记令牌；可选 script_id 初始化脚本动作；'
            'list/get 查看；enable/disable 启停；repair 查询远端并修复未完成操作；rotate_token 重置令牌；'
            'delete 删除远端指令和自己的绑定，需 confirm=true。id 为本工具返回的本地 ID。'
            "传 team_id、trigger（不带 /）创建事件入口；可不传 script_id，再用 script_binding 绑定 wake 与 prompt。传 script_id 可绑定脚本；文本参数在事件 data.text。"
            '请求地址统一从 Mattermost 管理页的斜杠命令设置读取，无需提供令牌或请求地址。'
            '不自动执行指令或脚本，不返回令牌。未知结果先 repair，不重复创建。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['list', 'get', 'save', 'enable', 'disable', 'repair', 'rotate_token', 'delete'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'id': {'type': 'string', 'description': '本地指令 ID；新建时不填'}, 'team_id': {'type': 'string', 'description': '创建指令的 Mattermost 团队 ID'}, 'trigger': {'type': 'string', 'description': '指令名称，不带 /，字母、数字、下划线或连字符'}, 'display_name': {'type': 'string', 'description': '显示名称，最多 64 字'}, 'description': {'type': 'string', 'description': '自动补全描述，最多 256 字'}, 'hint': {'type': 'string', 'description': '自动补全参数提示，最多 128 字'}, 'script_id': {'type': 'string', 'description': '可选，设置脚本动作；留空保留框架现有动作'}, 'params': {'type': 'object', 'additionalProperties': True, 'description': '传给脚本的固定参数；Slash 参数来自事件 text'}, 'user_id': {'type': 'string', 'description': '可选，仅接受此用户；留空不限'}, 'channel_id': {'type': 'string', 'description': '可选，仅接受此频道；留空不限'}, 'enabled': {'type': 'boolean', 'description': '是否启用此托管命令；停用不删除远端记录'}, 'confirm': {'type': 'boolean', 'description': 'delete 时仅在明确确认删除远端指令和本地绑定后为true'}, 'remote': {'type': 'boolean', 'description': 'list 时同时查询团队的远端指令，需 team_id'}}, 'required': ['action'], 'additionalProperties': False}, self.invoke)
        self.plugin.api('commands', self.catalog_api)
        self.plugin.api('commands', self.action_api, methods=('POST',))
        self.plugin.api('command-settings', self.settings_api, methods=('POST',))

    @property
    def server(self):
        return self.plugin.config.get('base_url', '').rstrip('/')

    @property
    def account(self):
        return hashlib.sha256((self.server + '\0' + self.plugin.config.get('token', '')).encode()).hexdigest()

    @property
    def callback_url(self):
        from .config import Settings
        return Settings.callback_url(self.plugin.config.get('slash_base_url', ''))

    def records(self):
        return self.plugin.state.get('slash_commands', {})

    def put(self, row):
        row['updated'] = time.time()
        records = self.records()
        records[row['id']] = row
        self.plugin.state.set('slash_commands', records)

    def public(self, row):
        data = {key: row.get(key) for key in PUBLIC_FIELDS}
        data['token_configured'] = bool(row.get('token'))
        data['current_account'] = row.get('account') == self.account
        data['callback_outdated'] = row.get('callback_url') != self.callback_url
        if not data['current_account']:
            data['status'] = 'account_changed'
        binding = self.current_binding(row)
        data['binding'] = binding
        data['script_id'] = binding.get('script_id', '') if binding and binding.get('target_kind', 'script') == 'script' else ''
        data['params'] = binding.get('params', {}) if data['script_id'] else {}
        # Command availability is an ingress property, independent of its downstream action.
        data['active'] = bool(row.get('status') == 'ready' and row.get('enabled') and
                              data['current_account'] and self.plugin.config.get('slash_enabled'))
        return data

    def get(self, key):
        if not isinstance(key, str) or key not in self.records():
            raise ValueError('本地指令不存在，请先列出指令')
        return self.records()[key]

    async def catalog_api(self, request):
        return self.catalog()

    def catalog(self):
        return {'commands': [self.public(row) for row in self.records().values()],
                'scripts': self.plugin.runtime.scripts.repo.list('scripts'),
                'settings': {'enabled': self.plugin.config.get('slash_enabled', False),
                             'base_url': self.plugin.config.get('slash_base_url', '')},
                'callback_url': self.callback_url,
                'server_url': self.server}

    async def settings_api(self, request):
        from .config import Settings
        data = await request.json()
        if not isinstance(data, dict) or set(data) != {'enabled', 'base_url'} or type(data['enabled']) is not bool:
            raise ValueError('斜杠命令设置格式无效')
        base = Settings.validate_slash_base(data['base_url'])
        if data['enabled'] and not base:
            raise ValueError('启用前请填写 SakuBot 基础地址')
        async with self.plugin.config_lock:
            self.plugin.config.update(slash_enabled=data['enabled'], slash_base_url=base)
            self.plugin.config.save()
        self.plugin.runtime.store.log('info', self.plugin.id, 'mattermost.command.settings_saved')
        return self.catalog()

    async def action_api(self, request):
        return await self.invoke(None, await request.json())

    async def api(self, method, path, body=None, query=None):
        # This private transport must never return its unredacted result to a tool or log.
        if not self.plugin.online or not self.plugin.http:
            raise RuntimeError('Mattermost 未连接')
        try:
            async with self.plugin.http.stream(method, 'api/v4/commands' + path,
                                                json=body, params=query) as response:
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise RuntimeError('远端指令列表过大')
                    chunks.append(chunk)
                if response.status_code >= 400:
                    raise CommandAPIError(response.status_code)
                return json.loads(b''.join(chunks)) if size else {}
        except (httpx.HTTPError, ValueError):
            raise RuntimeError('Mattermost 请求中断或响应无效；操作结果未知，请使用 repair 查询') from None

    @staticmethod
    def binding_id(row):
        return 'mmcmd_' + row['id']

    def suspend(self, row):
        self.plugin.runtime.scripts.delete('binding', self.binding_id(row), confirm=True)

    def current_binding(self, row):
        source = self.plugin.id + '.slash.' + row['trigger']
        return next((item for item in self.plugin.runtime.scripts.bindings()
                     if item['source'] == source), None)

    def script_references(self, identifier):
        # Current bindings are checked by the framework; only unfinished remote mutations
        # may still need a script which is not registered as a binding yet.
        return any(row.get('pending_binding', {}).get('target_kind', 'script') == 'script' and
                   row.get('pending_binding', {}).get('script_id') == identifier
                   for row in self.records().values() if row.get('pending_binding'))

    def prepare_binding(self, row, args, old):
        current = self.current_binding(old or row)
        fields = ('id', 'name', 'target_kind', 'script_id', 'source_params', 'params', 'enabled',
                  'prompt', 'on_failure', 'failure_threshold', 'cooldown_seconds', 'send_result_to_source')
        desired = {key: current[key] for key in fields if key in current} if current else None
        if args.get('script_id'):
            desired = {**(desired or {}), 'target_kind': 'script', 'script_id': args['script_id'],
                       'params': args.get('params', {}), 'enabled': current.get('enabled', True) if current else True}
        if desired is not None and desired.get('target_kind', 'script') == 'script' and 'params' in args:
            desired['params'] = args['params']
            script = self.plugin.runtime.scripts.repo.get(desired['script_id'])
            jsonschema.validate(desired['params'], script['parameters'])
        if desired is not None:
            desired.setdefault('id', self.binding_id(row))
            desired['name'] = '/' + row['trigger']
            desired['source'] = self.plugin.id + '.slash.' + row['trigger']
            desired['source_params'] = {key: row[key] for key in ('team_id', 'user_id', 'channel_id') if row.get(key)}
        # Journal the action snapshot before remote changes; repair never rebuilds a stale script reference.
        if desired is not None:
            row['pending_binding'] = desired
            row['pending_binding_revision'] = current.get('updated') if current else None
        else:
            row.pop('pending_binding', None)
            row.pop('pending_binding_revision', None)

    def validate(self, args, old=None):
        old = old or {}
        row = {**old, **{key: value for key, value in args.items()
                        if key in PUBLIC_FIELDS and key not in ('id', 'status', 'error', 'updated', 'command_id', 'callback_url', 'synced_at')}}
        row['id'] = old.get('id') or uuid.uuid4().hex[:12]
        row.setdefault('enabled', True)
        row.setdefault('params', {})
        for key, maximum in [('trigger', 64), ('display_name', 64), ('description', 256), ('hint', 128)]:
            value = row.get(key, '')
            if not isinstance(value, str) or len(value) > maximum:
                raise ValueError(key + ' 格式或长度无效')
            row[key] = value.strip()
        if not TRIGGER.fullmatch(row['trigger']):
            raise ValueError('指令名称须为 1～64 个字母、数字、下划线或连字符，不带 /')
        for key in ('team_id', 'user_id', 'channel_id'):
            row.setdefault(key, '')
            if (key == 'team_id' or row[key]) and (not isinstance(row[key], str) or not REMOTE_ID.fullmatch(row[key])):
                raise ValueError(key + ' 格式无效')
        if old and row['team_id'] != old['team_id']:
            raise ValueError('不能更换已有指令的团队，请新建指令')
        if type(row['enabled']) is not bool or not isinstance(row['params'], dict):
            raise ValueError('开关或脚本参数无效')
        if args.get('script_id'):
            script = self.plugin.runtime.scripts.repo.get(args['script_id'])
            jsonschema.validate(row['params'], script['parameters'])
        if len(json.dumps(row['params'], ensure_ascii=False)) > 50000:
            raise ValueError('脚本参数过大')
        row['callback_url'] = self.callback_url
        if not row['callback_url']:
            raise ValueError('请在 Mattermost → 斜杠命令中保存 SakuBot 基础地址')
        if any(item['id'] != row['id'] and item.get('server') == self.server and
               item['team_id'] == row['team_id'] and item['trigger'] == row['trigger']
               for item in self.records().values()):
            raise ValueError('同团队已有此指令的本地登记，请编辑或修复已有登记')
        return row

    def remote_body(self, row):
        return {'team_id': row['team_id'], 'trigger': row['trigger'], 'method': 'P',
                'url': row['callback_url'], 'display_name': row['display_name'] or row['trigger'],
                'description': row['description'], 'auto_complete': True,
                'auto_complete_desc': row['description'], 'auto_complete_hint': row['hint']}

    async def finish(self, row, remote):
        command_id = str(remote.get('id', ''))
        if not REMOTE_ID.fullmatch(command_id):
            raise RuntimeError('远端未返回有效指令 ID，请修复登记')
        if remote.get('creator_id') != self.plugin.bot_id or remote.get('team_id') != row['team_id']:
            raise ValueError('远端指令的账号或团队不匹配')
        row.update(command_id=command_id, bot_id=self.plugin.bot_id, account=self.account)
        if remote.get('token'):
            row['token'] = remote['token']
        self.put(row)
        from .command_sync import readback
        await readback(self, row)
        self.put(row)
        # All mutations hold config_lock, including the remote part of the operation.
        self.plugin.config['slash_enabled'] = True
        self.plugin.config.save()
        pending = row.get('pending_binding')
        if pending:
            current = next((item for item in self.plugin.runtime.scripts.repo.list('bindings') if item['id'] == pending['id']), None)
            revision = current.get('updated') if current else None
            if 'pending_binding_revision' not in row or revision == row['pending_binding_revision']:
                self.plugin.runtime.scripts.save_binding(pending)
            else:
                self.plugin.runtime.store.log('warning', self.plugin.id, 'mattermost.command.binding_changed',
                    data={'id': row['id'], 'reason': '事件动作已另行修改，保留框架当前配置'})
            row.pop('pending_binding', None)
            row.pop('pending_binding_revision', None)
        row.update(status='ready', error='')
        self.put(row)
        self.plugin.runtime.store.log('info', self.plugin.id, 'mattermost.command.synced',
            data={'id': row['id'], 'trigger': row['trigger']})
        return self.public(row)

    async def repair(self, row):
        if not row.get('command_id'):
            values = await self.api('GET', '', query={'team_id': row['team_id'], 'custom_only': 'true'})
            matches = [item for item in values if item.get('trigger') == row['trigger'] and
                       item.get('url') == row['callback_url'] and item.get('creator_id') == self.plugin.bot_id]
            if len(matches) != 1:
                raise ValueError('未唯一匹配到远端指令；不会自动重试创建，请检查远端后删除本地登记再新建')
            row['command_id'] = matches[0]['id']
            self.put(row)
        try:
            remote = await self.api('GET', '/' + row['command_id'])
        except CommandAPIError as exc:
            if exc.status == 404 and row.get('status') == 'deleting':
                return self.remove_local(row)
            raise
        if remote.get('creator_id') != self.plugin.bot_id or remote.get('team_id') != row['team_id']:
            raise ValueError('远端指令的账号或团队不匹配')
        if row.get('status') == 'deleting':
            await self.api('DELETE', '/' + row['command_id'])
            return self.remove_local(row)
        row['callback_url'] = self.callback_url
        if not row['callback_url']:
            raise ValueError('请先在斜杠命令页保存 SakuBot 基础地址')
        self.put(row)
        desired = self.remote_body(row)
        if any(remote.get(key) != value for key, value in desired.items()):
            remote = await self.api('PUT', '/' + row['command_id'], {**desired, 'id': row['command_id'], 'creator_id': remote['creator_id']})
        return await self.finish(row, remote)

    def remove_local(self, row):
        self.suspend(row)
        records = self.records()
        records.pop(row['id'], None)
        self.plugin.state.set('slash_commands', records)
        return {'deleted': row['id']}

    async def invoke(self, invocation, args) :
        if not isinstance(args, dict):
            raise ValueError('指令参数须为对象')
        action = args.get('action')
        if action == 'list':
            result = {'commands': [self.public(row) for row in self.records().values()],
                      'callback_url': self.callback_url}
            if args.get('remote'):
                team = args.get('team_id', '')
                if not isinstance(team, str) or not REMOTE_ID.fullmatch(team):
                    raise ValueError('请提供团队 ID')
                result['remote'] = redact(await self.api('GET', '', query={'team_id': team, 'custom_only': 'true'}))
            return result
        if action == 'get':
            return self.public(self.get(args.get('id')))
        if action not in ('save', 'enable', 'disable', 'repair', 'rotate_token', 'delete'):
            raise ValueError('指令操作无效')
        if action == 'delete' and args.get('confirm') is not True:
            raise ValueError('请确认删除指令')
        async with self.lock, self.plugin.config_lock:
            row = self.get(args['id']) if args.get('id') else None
            if row and row.get('server') != self.server:
                raise ValueError('指令属于其他 Mattermost 服务器，请切回原连接后操作')
            if not row and action != 'save':
                raise ValueError('请提供本地指令 ID')
            if row and row.get('account') != self.account and action not in ('repair', 'delete'):
                raise ValueError('连接账号已变化，请先修复登记')
            if row and row.get('status') != 'ready' and action not in ('repair', 'delete'):
                raise ValueError('上次操作尚未完成，请先修复登记')
            if action == 'save':
                creating = row is None
                old = row
                row = self.validate(args, old)
                self.prepare_binding(row, args, old)
                row.setdefault('server', self.server)
                row.setdefault('account', self.account)
                if creating:
                    if len(self.records()) >= 500:
                        raise ValueError('本地指令登记已达 500 个，请先删除不再使用的指令')
                    # A preflight detects existing names; never adopt unrelated commands.
                    existing = await self.api('GET', '', query={'team_id': row['team_id'], 'custom_only': 'true'})
                    if any(item.get('trigger') == row['trigger'] for item in existing):
                        raise ValueError('远端已有同名指令，请使用其他名称')
                row.update(status='creating' if creating else 'updating', error='')
                self.put(row)
            elif action in ('enable', 'disable'):
                row['enabled'] = action == 'enable'
                if row['enabled']:
                    self.validate({}, row)
                    self.plugin.config['slash_enabled'] = True
                    self.plugin.config.save()
                self.put(row)
                return self.public(row)
            else:
                row['error'] = ''
                if action in ('delete', 'rotate_token'):
                    row['status'] = 'deleting' if action == 'delete' else 'rotating_token'
                elif row.get('status') != 'deleting':
                    row['status'] = 'repairing'
                self.put(row)
            try:
                if action == 'save':
                    body = self.remote_body(row)
                    if creating:
                        remote = await self.api('POST', '', body)
                    else:
                        body.update(id=row['command_id'], creator_id=row['bot_id'])
                        remote = await self.api('PUT', '/' + row['command_id'], body)
                    result = await self.finish(row, remote)
                elif action == 'repair':
                    result = await self.repair(row)
                elif action == 'rotate_token':
                    remote = await self.api('GET', '/' + row['command_id'])
                    if remote.get('creator_id') != self.plugin.bot_id:
                        raise ValueError('指令不属于当前账号')
                    row['token'] = ''
                    self.put(row)
                    token = await self.api('PUT', '/' + row['command_id'] + '/regen_token')
                    remote['token'] = token.get('token', '')
                    result = await self.finish(row, remote)
                else:
                    if row.get('command_id'):
                        try:
                            remote = await self.api('GET', '/' + row['command_id'])
                            if remote.get('creator_id') != self.plugin.bot_id:
                                raise ValueError('指令不属于当前账号')
                            await self.api('DELETE', '/' + row['command_id'])
                        except CommandAPIError as exc:
                            if exc.status != 404:
                                raise
                    else:
                        # Resolve a timed-out create before deleting its journal.
                        values = await self.api('GET', '', query={'team_id': row['team_id'], 'custom_only': 'true'})
                        if any(item.get('trigger') == row['trigger'] for item in values):
                            raise ValueError('远端仍有同名指令，请先修复登记再删除')
                    result = self.remove_local(row)
                self.plugin.runtime.store.log('info', self.plugin.id, 'mattermost.command.' + action,
                    data={'id': row['id'], 'command_id': row.get('command_id'), 'trigger': row['trigger']})
                return result
            except Exception as exc:
                row['error'] = str(exc)[:240] if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
                self.put(row)
                self.plugin.runtime.store.log('warning', self.plugin.id, 'mattermost.command.pending',
                    data={'id': row['id'], 'action': action, 'error': row['error']})
                return {'complete': False, 'command': self.public(row), 'error': row['error'],
                        'next_action': 'repair'}

    def authentication_error(self, token, data):
        from .command_auth import rejection
        return rejection(self, token, data)

    def authenticate(self, token, data):
        return not self.authentication_error(token, data)
