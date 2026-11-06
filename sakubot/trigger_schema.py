"""Public event documentation helpers and declaration-time contract validation."""
import copy
import jsonschema
from .automation.repository import schema


def field(kind, description, **constraints):
    return {'type': kind, 'description': description, **constraints}


def event_schema(description, properties, example, required=()):
    return {'type': 'object', 'description': description, 'properties': properties,
            'required': list(required), 'examples': [example]}


def documented(parameters, event, identifier, id_description):
    parameters, event = copy.deepcopy(schema(parameters)), copy.deepcopy(schema(event))
    def walk(node, path, named=False):
        if not isinstance(node, dict):
            raise ValueError(path + ' 必须为 Schema 对象')
        if named and (not isinstance(node.get('description'), str) or not node['description'].strip()):
            raise ValueError(path + ' 缺少变量 description 说明')
        if named and not node.get('type') and not any(key in node for key in ('oneOf', 'anyOf', 'allOf')):
            raise ValueError(path + ' 缺少变量类型')
        if node.get('$ref'):
            raise ValueError(path + ' 请内联字段定义，不支持引用式事件文档')
        values = node.get('enum', [])
        meanings = node.get('x-enum-descriptions', {})
        if values and (not isinstance(meanings, dict) or any(not isinstance(meanings.get(str(value)), str) or not meanings[str(value)].strip() for value in values)):
            raise ValueError(path + ' 需用 x-enum-descriptions 逐项说明枚举值')
        for key, child in node.get('properties', {}).items():
            walk(child, path + '.' + key, True)
        for pattern, child in node.get('patternProperties', {}).items():
            walk(child, path + '.pattern[' + pattern + ']', True)
        if isinstance(node.get('items'), dict):
            walk(node['items'], path + '[]', True)
        elif isinstance(node.get('items'), list):
            for index, child in enumerate(node['items']):
                walk(child, f'{path}[{index}]', True)
        if isinstance(node.get('additionalProperties'), dict):
            walk(node['additionalProperties'], path + '.*', True)
        for keyword in ('oneOf', 'anyOf', 'allOf'):
            for index, child in enumerate(node.get(keyword, [])):
                walk(child, f'{path}.{keyword}[{index}]')
        for key, child in node.get('$defs', {}).items():
            walk(child, path + '.$defs.' + key)
    walk(parameters, 'parameters')
    walk(event, 'event_schema', True)
    if not isinstance(id_description, str) or not id_description.strip():
        raise ValueError(identifier + ' 必须提供 id_description，说明实际事件 ID，泛事件须解释动态部分')
    examples = event.get('examples')
    if not isinstance(examples, list) or not examples or not all(isinstance(item, dict) for item in examples):
        raise ValueError(identifier + ' 必须提供至少一个完整 payload examples 示例')
    for index, example in enumerate(examples):
        try:
            jsonschema.Draft7Validator(event).validate(example)
        except jsonschema.ValidationError as exc:
            raise ValueError(f'{identifier} 的 examples[{index}] 与 event_schema 不符：' + exc.message) from None
        missing = set(event.get('properties', {})) - set(example)
        if missing:
            raise ValueError(f'{identifier} 的 examples[{index}] 缺少已声明字段：' + ', '.join(sorted(missing)))
    return parameters, event
