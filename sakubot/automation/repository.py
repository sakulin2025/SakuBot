import ast
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

import jsonschema
from sakubot.store import encode


ID = re.compile(r'[a-zA-Z0-9_-]{1,64}')


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('脚本 ID 无效')
    return value


def schema(value):
    if not isinstance(value, dict) or value.get('type') != 'object':
        raise ValueError('参数定义须为 object JSON Schema')
    jsonschema.Draft7Validator.check_schema(value)
    if len(encode(value)) > 50000:
        raise ValueError('参数定义过大')
    return value


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(value, encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Repository:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store
        self.root = runtime.config.root / 'scripts'
        self.data_root = runtime.config.root / 'script_data'
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.store.db.executescript('''
        CREATE TABLE IF NOT EXISTS automation_scripts (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS automation_bindings (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS automation_runs (
          id TEXT PRIMARY KEY, script_id TEXT NOT NULL, binding_id TEXT NOT NULL, version TEXT NOT NULL,
          status TEXT NOT NULL, queued REAL NOT NULL, started REAL, finished REAL,
          input TEXT NOT NULL, output TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
          logs TEXT NOT NULL DEFAULT '', uid TEXT UNIQUE, wake_id INTEGER);
        CREATE INDEX IF NOT EXISTS automation_queue ON automation_runs(status,queued);
        CREATE INDEX IF NOT EXISTS automation_script_runs ON automation_runs(script_id,queued);
        ''')
        self.store.execute("UPDATE automation_runs SET status='interrupted',finished=?,error='进程中断，未自动重放；外部操作可能已执行' WHERE status='running'", (time.time(),))

    def list(self, table):
        if table not in ('scripts', 'bindings'):
            raise ValueError('类型无效')
        return [json.loads(row['data']) for row in self.store.rows('SELECT data FROM automation_' + table + ' ORDER BY id')]

    def get(self, key):
        row = self.store.one('SELECT data FROM automation_scripts WHERE id=?', (identifier(key),))
        if not row:
            raise ValueError('脚本不存在')
        return json.loads(row['data'])

    def read(self, key, version=''):
        item = self.get(key)
        version = version or item['version']
        if not re.fullmatch(r'[a-f0-9]{32}', version):
            raise ValueError('版本无效')
        manifest = self.root / key / 'revisions' / (version + '.json')
        if manifest.is_file():
            item = json.loads(manifest.read_text())
        return {**item, 'version': version, 'code': (self.root / key / 'revisions' / (version + '.py')).read_text()}

    async def save(self, data):
        if not isinstance(data, dict):
            raise ValueError('脚本格式无效')
        key = identifier(data.get('id') or uuid.uuid4().hex[:12])
        try:
            old = self.get(key)
        except ValueError:
            old = None
        if old and data.get('expected_version') != old['version']:
            raise ValueError('脚本已变化，请重新读取后保存')
        name = data.get('name', old['name'] if old else '')
        code = data.get('code')
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError('名称为 1～100 字')
        if not isinstance(code, str) or len(code.encode()) > 200000:
            raise ValueError('代码须为不超过 200 KB 的文本')
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise ValueError(f'代码语法错误，第 {exc.lineno} 行：{exc.msg}') from None
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'main' for node in tree.body):
            raise ValueError('须定义 main(ctx)')
        params = schema(data.get('parameters', old.get('parameters', {'type':'object','properties':{}}) if old else {'type':'object','properties':{}}))
        sources = data.get('event_sources', old.get('event_sources', list(dict.fromkeys(row['source'] for row in self.list('bindings') if row.get('script_id')==key))) if old else [])
        plugins = data.get('tool_plugins', old.get('tool_plugins') if old else None)
        if (not isinstance(sources, list) or len(sources)>100 or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_.*:-]{1,256}',v) for v in sources)
                or (plugins is not None and (not isinstance(plugins,list) or any(not isinstance(v,str) or not re.fullmatch(r'[a-zA-Z_]\w*',v) for v in plugins)))):
            raise ValueError('event_sources 或 tool_plugins 格式无效')
        hard = data.get('hard', False)
        if type(hard) is not bool:
            raise ValueError('hard 必须为布尔值')
        from .script_check import check, ScriptDiagnosticsError
        report = await check(self.runtime, code, sources=sources, parameters=params, tool_plugins=plugins)
        reason = data.get('hard_reason','')
        if not report['ok']:
            if (not report.get('syntax_ok') or not report.get('checker_available') or not hard):
                raise ScriptDiagnosticsError(report)
            if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:
                raise ValueError('强制保存须提供 1～2000 字的 hard_reason')
        # Checking yields to other requests; recheck optimistic version before any writes.
        if old and self.get(key)['version'] != old['version']:
            raise ValueError('检查期间脚本已被修改，请重新读取后保存')
        if not old and self.store.one('SELECT id FROM automation_scripts WHERE id=?',(key,)):
            raise ValueError('检查期间同名脚本已被创建，请重新读取')
        contract = {'event_sources':sources, 'tool_plugins':plugins, 'event_contracts':report['event_contracts'],
            'sdk_hash':report['sdk_hash'], 'validation':{'checker':report['checker'], 'checked_at':time.time(),
                'forced':hard and not report['ok'], 'reason':reason if hard and not report['ok'] else '', 'diagnostics':report['diagnostics']}}
        description = data.get('description', old.get('description', '') if old else '')
        if not isinstance(description, str) or len(description) > 4000:
            raise ValueError('描述最多 4000 字')
        timeout = data.get('timeout', old.get('timeout', 120) if old else 120)
        enabled = data.get('enabled', old.get('enabled', True) if old else True)
        concurrency = data.get('concurrency', old.get('concurrency', 'merge') if old else 'merge')
        if type(timeout) is not int or not 1 <= timeout <= 86400 or type(enabled) is not bool or concurrency not in ('queue','merge','skip'):
            raise ValueError('超时、启用状态或并发策略无效')
        failure = {key: data.get(key, old.get(key, default) if old else default) for key, default in
                   [('on_failure','none'),('failure_threshold',1),('cooldown_seconds',3600),('send_result_to_source',True)]}
        if failure['on_failure'] not in ('none','wake','notify') or type(failure['send_result_to_source']) is not bool:
            raise ValueError('失败处理或报告开关无效')
        if type(failure['failure_threshold']) is not int or not 1 <= failure['failure_threshold'] <= 100 or type(failure['cooldown_seconds']) is not int or not 30 <= failure['cooldown_seconds'] <= 2592000:
            raise ValueError('失败阈值或冷却时间无效')
        version = hashlib.sha256((code + encode({'parameters':params,'name':name,'description':description,'timeout':timeout,'enabled':enabled,'concurrency':concurrency,'sdk_hash':report['sdk_hash'],'event_sources':sources,'tool_plugins':plugins,'forced':contract['validation']['forced'],'force_reason':contract['validation']['reason'],**failure})).encode()).hexdigest()[:32]
        item = {'id':key,'name':name.strip(),'description':description,'parameters':params,'version':version,
                'timeout':timeout,'enabled':enabled,'concurrency':concurrency,'updated':time.time(),**failure,**contract}
        folder = self.root / key
        atomic(folder / 'revisions' / (version + '.types.py'), report['sdk'])
        atomic(folder / 'revisions' / (version + '.py'), code)
        atomic(folder / 'revisions' / (version + '.json'), encode(item))
        atomic(folder / 'main.py', code)
        atomic(folder / 'script.json', encode(item))
        self.store.execute('INSERT OR REPLACE INTO automation_scripts VALUES (?,?)', (key, encode(item)))
        if contract['validation']['forced']:
            self.store.log('warning','scripts','script.validation.forced',data={'script_id':key,'version':version,
                'reason':reason,'diagnostics':report['diagnostics'],'sdk_hash':report['sdk_hash']})
        return item

    def revisions(self, key):
        self.get(key)
        return [{'version':p.stem,'at':p.stat().st_mtime} for p in sorted((self.root/key/'revisions').glob('*.py'), key=lambda p:p.stat().st_mtime, reverse=True) if re.fullmatch(r'[a-f0-9]{32}', p.stem)]

    def state(self, key):
        return self.store.kv_get('automation:state:' + key, {})

    def set_state(self, key, values):
        if not isinstance(values, dict) or len(encode(values).encode()) > 262144:
            raise ValueError('脚本状态须为不超过 256 KiB 的 JSON 对象')
        atomic(self.data_root / key / 'state.json', encode(values))
        self.store.kv_set('automation:state:' + key, values)
