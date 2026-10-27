"""Declarative settings remain editable without starting a plugin."""
import inspect
import json
import re
from urllib.parse import urlsplit

import httpx
import jsonschema

from .plugin_packages import program_path


def declaration(runtime, identifier):
    plugin = next((p for p in runtime.registry.plugins if p.id == identifier), None)
    dynamic = getattr(plugin, '_settings_form', None)
    try:
        path = program_path(runtime.config.root, identifier)
        manifest = path / 'plugin.json' if path.is_dir() else path.with_suffix('.json')
        metadata = json.loads(manifest.read_text()) if manifest.exists() else {}
    except (ValueError, OSError):
        metadata = {}
    static = metadata.get('settings')
    if not static and not dynamic:
        return None
    result = dict(static or {})
    if dynamic:
        result = {**result, **{k: v for k, v in dynamic.items() if k != 'fields'}}
        # Manifest fields supply placeholders/defaults even when the runtime declaration is concise.
        saved = {f['key']: f for f in result.get('fields', [])}
        result['fields'] = [{**f, **saved.get(f['key'], {})} for f in dynamic['fields']]
    return result


def configuration(runtime, identifier, spec):
    plugin = next((p for p in runtime.registry.plugins if p.id == identifier), None)
    config = getattr(plugin, '_configuration', None)
    path = runtime.config.root / 'plugin_data' / identifier / 'config.json'
    data = json.loads(path.read_text()) if path.exists() else {}
    defaults = {f['key']: f['default'] for f in spec['fields'] if 'default' in f}
    return {**defaults, **(dict(config) if config is not None else data)}, path, plugin


def missing(spec, values):
    absent = [f['label'] for f in spec['fields'] if f.get('required') and (values.get(f['key']) is None or (isinstance(values.get(f['key']), str) and not values[f['key']].strip()))]
    for group in spec.get('required_any', []):
        if not any(all(values.get(key) not in (None, '') for key in keys) for keys in group):
            absent.append('认证信息')
    return absent


def public(runtime, identifier):
    spec = declaration(runtime, identifier)
    if spec is None:
        raise ValueError('插件未声明设置表单')
    values, _, _ = configuration(runtime, identifier, spec)
    result = {}
    for field in spec['fields']:
        key = field['key']
        result[key] = '' if field['type'] == 'secret' else values.get(key, '')
        if field['type'] == 'secret':
            result[key + '_configured'] = bool(values.get(key))
    return {'fields': spec['fields'], 'values': result, 'required_any': spec.get('required_any', []), 'requires_connection': bool(spec.get('connection') or spec.get('validate'))}


def validate_fields(fields, values):
    from .plugin_support import fields_schema
    if not isinstance(values, dict):
        raise ValueError('设置必须是对象')
    try:
        jsonschema.Draft202012Validator(fields_schema(fields)).validate(values)
    except jsonschema.ValidationError as exc:
        key = next(iter(exc.absolute_path), '')
        label = next((f['label'] for f in fields if f['key'] == key), '设置')
        raise ValueError(label + '格式无效，请检查必填项、类型和取值范围') from None
    for f in fields:
        value = values.get(f['key'])
        if not isinstance(value, str) or not value:
            continue
        if f.get('required') and not value.strip():
            raise ValueError(f['label'] + '不能为空')
        if f['type'] == 'secret' and any(c in value for c in '\r\n'):
            raise ValueError(f['label'] + '不能包含换行')
        if f.get('format') in ('http-url', 'https-host'):
            try:
                parsed = urlsplit(('https://' + value) if f['format'] == 'https-host' and '://' not in value else value)
                port = parsed.port
                valid = parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not (parsed.username or parsed.password or parsed.query or parsed.fragment) and not any(c.isspace() for c in value)
                if f['format'] == 'https-host':
                    valid = valid and parsed.scheme == 'https' and parsed.path in ('', '/') and port in (None, 443)
                if not valid:
                    raise ValueError()
            except ValueError:
                raise ValueError(f['label'] + ('请填写 HTTPS 根域名' if f['format'] == 'https-host' else '请填写完整的 HTTP/HTTPS 地址')) from None
        if f.get('pattern') and not re.fullmatch(f['pattern'], value):
            raise ValueError(f['label'] + '格式无效')


async def probe(spec, values):
    connection = spec.get('connection')
    if not connection:
        return
    kind = connection.get('kind', 'http')
    base = str(values[connection.get('url_field', 'base_url')]).rstrip('/')
    headers, params = {}, {}
    if kind == 'qweather':
        base = base if '://' in base else 'https://' + base
        headers['X-QW-Api-Key'] = values['key']
        params['location'] = values['default_city']
    elif connection.get('token_field'):
        token = str(values.get(connection['token_field'], '')).removeprefix('Bearer ').strip()
        headers[connection.get('token_header', 'Authorization')] = connection.get('token_prefix', 'Bearer ') + token
    if connection.get('strip_suffix'):
        base = base.removesuffix(connection['strip_suffix'])
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
            if kind == 'alist':
                token = values.get('token')
                if not token:
                    login = await client.post(base + '/api/auth/login', json={'username': values['username'], 'password': values['password']})
                    if login.status_code != 200 or login.json().get('code') != 200:
                        raise ValueError('账号或密码验证失败，配置未保存')
                    token = login.json()['data']['token']
                headers['Authorization'] = token
            response = await client.get(base + connection['path'], headers=headers, params=params)
            if response.status_code in (401, 403):
                raise ValueError('认证失败，请检查密钥或账号，配置未保存')
            if response.status_code != 200:
                raise ValueError('连接验证失败（HTTP ' + str(response.status_code) + '），配置未保存')
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('接口返回格式不匹配，配置未保存')
            if kind == 'qweather' and (str(data.get('code')) != '200' or not data.get('location')):
                raise ValueError('天气密钥或默认城市验证失败，配置未保存')
            if kind == 'alist' and data.get('code') != 200:
                raise ValueError('AList 认证失败，配置未保存')
            for path in connection.get('required_paths', []):
                found = data
                for key in path.split('.'):
                    found = found.get(key) if isinstance(found, dict) else None
                if found is None:
                    raise ValueError('接口返回格式不匹配，配置未保存')
    except httpx.HTTPError:
        raise ValueError('无法连接服务或连接超时，配置未保存') from None
    except (KeyError, json.JSONDecodeError):
        raise ValueError('接口返回格式不匹配，配置未保存') from None


async def save(runtime, identifier, values):
    spec = declaration(runtime, identifier)
    if spec is None:
        raise ValueError('插件未声明设置表单')
    current, path, plugin = configuration(runtime, identifier, spec)
    fields = spec['fields']
    # Blank secrets keep the saved value. Everything else is validated before any write.
    candidate = dict(current)
    if not isinstance(values, dict):
        raise ValueError('设置必须是对象')
    clean = {}
    for f in fields:
        key = f['key']
        value = values.get(key, current.get(key, f.get('default', '')))
        if isinstance(value, str) and f['type'] != 'text':
            value = value.strip()
        if f['type'] == 'secret' and value == '':
            value = current.get(key, '')
        clean[key] = value
    if set(values) - {f['key'] for f in fields}:
        raise ValueError('包含未声明的设置字段')
    validate_fields(fields, clean)
    candidate.update(clean)
    if missing(spec, candidate):
        raise ValueError('请补全：' + '、'.join(missing(spec, candidate)))
    await probe(spec, candidate)
    validator = spec.get('validate')
    if callable(validator):
        result = validator(dict(candidate))
        if inspect.isawaitable(result):
            result = await result
        if result is False:
            raise ValueError('插件配置校验未通过')
    latest, _, _ = configuration(runtime, identifier, spec)
    if latest != current:
        raise ValueError('设置已发生变化，请重新打开后保存')
    runtime.config.atomic(path, json.dumps(candidate, ensure_ascii=False, indent=2))
    config = getattr(plugin, '_configuration', None)
    if config is not None:
        config.clear()
        config.update(candidate)
    callback = spec.get('on_saved')
    if callable(callback):
        try:
            result = callback()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            runtime.store.log('error', identifier, 'settings.callback.failed', data={'error': type(exc).__name__})
    runtime.registry.revision = __import__('uuid').uuid4().hex
    return public(runtime, identifier)
