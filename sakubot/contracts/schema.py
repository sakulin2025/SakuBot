"""TypedDict/Annotated contracts to JSON Schema, without executing user scripts."""
import copy
import enum
import types
import typing as t


def schema_from_type(annotation, *, described=True, _seen=()):
    origin, args = t.get_origin(annotation), t.get_args(annotation)
    metadata = {}
    if origin is t.Annotated:
        for item in args[1:]:
            if isinstance(item, str):
                metadata['description'] = item
            elif isinstance(item, dict):
                metadata.update(copy.deepcopy(item))
        result = schema_from_type(args[0], described=described, _seen=_seen)
    elif origin in (t.Required, t.NotRequired):
        result = schema_from_type(args[0], described=described, _seen=_seen)
    elif t.is_typeddict(annotation):
        if annotation in _seen:
            raise ValueError('不支持递归 TypedDict，请将动态内容声明为 dict[str, object] 并说明边界')
        properties, required = {}, []
        for key, value in t.get_type_hints(annotation, include_extras=True).items():
            properties[key] = schema_from_type(value, described=described, _seen=(*_seen, annotation))
            if described and not str(properties[key].get('description', '')).strip():
                raise ValueError(annotation.__name__ + '.' + key + ' 需用 Annotated 提供字段说明')
            unwrapped = value
            while t.get_origin(unwrapped) is t.Annotated:
                unwrapped = t.get_args(unwrapped)[0]
            wrapper = t.get_origin(unwrapped)
            if wrapper is t.Required or (wrapper is not t.NotRequired and key in annotation.__required_keys__):
                required.append(key)
        result = {'type':'object', 'properties':properties, 'required':required, 'additionalProperties':False}
        if annotation.__doc__ and not annotation.__doc__.startswith('dict('):
            result['description'] = annotation.__doc__.strip()
    elif origin in (t.Union, types.UnionType):
        result = {'anyOf':[schema_from_type(item, described=described, _seen=_seen) for item in args]}
    elif origin is t.Literal:
        values = list(args)
        kinds = list(dict.fromkeys('null' if item is None else 'boolean' if isinstance(item,bool) else 'integer' if isinstance(item,int) else 'number' if isinstance(item,float) else 'string' for item in values))
        result = {'type':kinds[0] if len(kinds)==1 else kinds, 'enum':values}
    elif isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        result = schema_from_type(t.Literal[tuple(item.value for item in annotation)], described=described, _seen=_seen)
    elif annotation in (str, int, float, bool, type(None)):
        result = {'type':{str:'string',int:'integer',float:'number',bool:'boolean',type(None):'null'}[annotation]}
    elif origin in (list, tuple) or annotation in (list, tuple):
        if not args:
            raise ValueError('数组需声明元素类型，例如 list[str]')
        result = {'type':'array','items':schema_from_type(args[0], described=described, _seen=_seen)}
    elif origin is dict:
        if len(args)!=2 or args[0] is not str:
            raise ValueError('字典需声明为 dict[str, 值类型]')
        result = {'type':'object','additionalProperties':True if args[1] is object else schema_from_type(args[1], described=described, _seen=_seen)}
    elif annotation is object:
        result = {}
    else:
        raise ValueError('不支持或不完整的类型：' + str(annotation))
    result.update(metadata)
    return result


def contract_kind(schema):
    if not schema:
        return 'missing'
    branches = schema.get('anyOf') or schema.get('oneOf')
    if branches:
        kinds = {contract_kind(item) for item in branches}
        return 'fixed' if kinds == {'fixed'} else 'dynamic' if kinds == {'dynamic'} else 'mixed'
    if schema.get('type') == 'object' and not schema.get('properties'):
        return 'dynamic'
    if schema.get('type') == 'array':
        return contract_kind(schema.get('items', {}))
    return 'fixed'
