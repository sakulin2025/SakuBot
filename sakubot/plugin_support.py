"""Public conveniences for trusted local extensions."""
import asyncio
import copy
import inspect
import json
import re
import types
import typing
from pathlib import Path

import jsonschema


class PluginState:
    def __init__(self, plugin):
        self.plugin = plugin

    def get(self, key, default=None):
        return self.plugin.runtime.store.kv_get(self.plugin.id + ':' + key, default)

    def set(self, key, value):
        self.plugin.runtime.store.kv_set(self.plugin.id + ':' + key, value)
        return value


class PluginConfig(dict):
    def __init__(self, plugin, defaults=None, secrets=()):
        self.path = plugin.data_dir / 'config.json'
        self.plugin, self.secrets = plugin, set(secrets)
        data = json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else {}
        if not isinstance(data, dict):
            raise ValueError('插件配置必须是对象')
        super().__init__({**copy.deepcopy(defaults or {}), **data})

    def save(self):
        self.plugin.runtime.config.atomic(self.path, json.dumps(self, ensure_ascii=False, indent=2))

    def public(self, fields=None):
        names = fields if fields is not None else self.keys()
        result = {key: copy.deepcopy(self.get(key)) for key in names if key not in self.secrets}
        for key in self.secrets:
            if key in names:
                result[key] = ''
                result[key + '_configured'] = bool(self.get(key))
        return result

    def patch(self, data, schema):
        try:
            jsonschema.Draft202012Validator(schema).validate(data)
        except jsonschema.ValidationError as exc:
            raise ValueError('配置字段无效：' + '.'.join(str(part) for part in exc.absolute_path)) from None
        updated = {key: value for key, value in data.items() if key not in self.secrets or value != ''}
        self.update(updated)
        self.save()


def schema_for(annotation):
    origin, arguments = typing.get_origin(annotation), typing.get_args(annotation)
    if origin in (typing.Union, types.UnionType):
        return {'anyOf': [schema_for(item) for item in arguments]}
    if annotation in (str, int, float, bool, type(None)):
        return {'type': {str: 'string', int: 'integer', float: 'number', bool: 'boolean', type(None): 'null'}[annotation]}
    if annotation is dict or origin is dict:
        return {'type': 'object', 'additionalProperties': True}
    if annotation is list or origin is list:
        return {'type': 'array', 'items': schema_for(arguments[0]) if arguments else {}}
    return {}


def register_function(plugin, handler, name=None, description=None):
    signature = inspect.signature(handler)
    hints = typing.get_type_hints(handler)
    doc = inspect.getdoc(handler) or ''
    docs = dict(re.findall(r'^\s+(\w+)\([^)]*\):\s*(.+)$', doc, re.MULTILINE))
    properties, required = {}, []
    for key, value in signature.parameters.items():
        if key == 'invocation':
            continue
        item = schema_for(hints.get(key, str))
        if key in docs:
            item['description'] = docs[key]
        if value.default is inspect.Parameter.empty:
            required.append(key)
        else:
            if value.default is None and item.get('type') != 'null':
                item = {'anyOf': [item, {'type': 'null'}]}
            item['default'] = value.default
        properties[key] = item
    async def invoke(invocation, args):
        arguments = dict(args)
        if 'invocation' in signature.parameters:
            arguments['invocation'] = invocation
        result = await handler(**arguments) if inspect.iscoroutinefunction(handler) else await asyncio.to_thread(handler, **arguments)
        # Functions may deliberately return text; no implicit JSON decoding.
        return result
    plugin.tool(name or handler.__name__, description or doc.split('Args:')[0].strip(),
        {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}, invoke)
    return handler


def management(plugin, title, sections, state, action, *, icon='plugins', order=50):
    from .components import builtin
    settings = next((s for s in sections if s['id'] == 'config' and s['kind'] == 'form'), None) if not builtin(plugin.id) else None
    if settings:
        plugin.settings_form(settings['fields'], on_saved=getattr(plugin, 'settings_saved', None))
        sections = [s for s in sections if s is not settings]
    async def read(request):
        result = state()
        if inspect.isawaitable(result):
            result = await result
        return {'title': title, 'sections': sections, **result}
    async def write(request):
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError('请求必须为对象')
        if settings and payload.get('section') == 'config':
            from .plugin_settings import save
            await save(plugin.runtime, plugin.id, payload.get('value', {}))
            return {'result': {'saved': True}, 'state': await read(request)}
        if payload.get('action') == 'save':
            section = next((s for s in sections if s['id'] == payload.get('section')), None)
            if section is None:
                raise ValueError('表单不存在')
            from .plugin_settings import validate_fields
            validate_fields(section.get('fields', []), payload.get('value', {}))
            references = [f for f in section.get('fields', []) if f.get('options_from')]
            if references:
                snapshot = state()
                if inspect.isawaitable(snapshot):
                    snapshot = await snapshot
                for field in references:
                    records = snapshot.get('data', {}).get(field['options_from'], [])
                    if payload.get('value', {}).get(field['key']) not in {row.get('id', row.get('mac')) for row in records}:
                        raise ValueError(field['label'] + '不存在，请重新选择')
        result = action(payload)
        if inspect.isawaitable(result):
            result = await result
        return {'result': result, 'state': await read(request)}
    plugin.api('manage', read)
    plugin.api('manage', write, methods=('POST',))
    directory = Path(inspect.getfile(type(plugin))).parent
    plugin.page('manage', title, directory / 'web' / 'dist', icon=icon, order=order)


def field(key, label, type='string', **options):
    hints = {'base_url': '填写完整服务地址，如 http://192.168.1.10:8123', 'host': '填写服务控制台分配的域名',
        'token': '粘贴访问令牌，不包含 Bearer 前缀', 'key': '粘贴 API Key', 'default_city': '填写城市名、Location ID 或 经度,纬度',
        'name': '填写便于识别的名称', 'alias': '填写日常称呼，可留空', 'description': '填写用途或需要 AI 记住的信息，可留空',
        'address': '填写 IP 或域名，非默认端口按服务格式填写', 'username': '填写登录用户名', 'password': '填写登录密码',
        'target': 'main、private:QQ号 或 group:群号', 'content': '填写需要保存的内容', 'path_password': '填写目录访问密码，可留空',
        'public_url': '填写用于外部访问的完整地址，可留空', 'group': '填写设备所属分组，可留空'}
    if type == 'select' and options.get('options_from'):
        options.setdefault('required', True)
    placeholder = hints.get(key, ('请选择' if type == 'select' else '请输入') + label)
    return {'key': key, 'label': label, 'type': type, 'placeholder': placeholder, **options}


def collection(id, label, fields, *, key='id', create=True, edit=True, remove=True, **options):
    return {'id': id, 'label': label, 'kind': 'table', 'fields': fields, 'key': key,
        'create': create, 'edit': edit, 'remove': remove, **options}


def settings_section(fields, label='连接设置', id='config'):
    return {'id': id, 'label': label, 'kind': 'form', 'fields': fields}


def fields_schema(fields):
    properties = {}
    for item in fields:
        if item.get('readonly'):
            continue
        schema = {'type': 'integer' if item['type'] == 'number' else 'boolean' if item['type'] == 'boolean' else 'string'}
        if schema['type'] == 'string':
            schema['maxLength'] = item.get('max_length', 100000 if item['type'] == 'text' else 8192)
            if item.get('required'):
                schema['minLength'] = 1
            if item.get('pattern'):
                schema['pattern'] = item['pattern']
        if item['type'] == 'select' and item.get('options'):
            schema['enum'] = [option['value'] for option in item['options']]
        for source, destination in (('min', 'minimum'), ('max', 'maximum')):
            if source in item:
                schema[destination] = item[source]
        properties[item['key']] = schema
    return {'type': 'object', 'properties': properties, 'additionalProperties': False,
        'required': [item['key'] for item in fields if item.get('required') and not item.get('readonly')]}
