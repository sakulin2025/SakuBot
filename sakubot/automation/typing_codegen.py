"""Deterministic, importable Python types generated from registered contracts."""
import keyword
import re

HEADER = 'from __future__ import annotations\nfrom typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias\n'


def safe_name(value):
    result = re.sub(r'\W', '_', value)
    return ('_' + result) if not result or result[0].isdigit() or keyword.iskeyword(result) else result


class TypeWriter:
    def __init__(self):
        self.lines = [HEADER]
        self.index = 0

    def type(self, schema, hint='Value'):
        if not isinstance(schema, dict) or not schema:
            return 'object'
        branches = schema.get('anyOf') or schema.get('oneOf')
        if branches:
            value = ' | '.join(dict.fromkeys(self.type(row, hint) for row in branches))
        elif 'enum' in schema and all(item is None or isinstance(item,(str,int,bool)) for item in schema['enum']):
            value = 'Literal[' + ', '.join(repr(item) for item in schema['enum']) + ']'
        elif isinstance(schema.get('type'),list):
            value = ' | '.join(dict.fromkeys(self.type({**schema,'type':kind},hint) for kind in schema['type']))
        elif schema.get('type')=='object' and 'properties' in schema:
            self.index += 1
            name = safe_name(hint) + str(self.index)
            fields = []
            for key, child in schema['properties'].items():
                typ = self.type(child, hint + '_' + key)
                wrapper = 'Required' if key in schema.get('required',[]) else 'NotRequired'
                fields.append(repr(key) + ': ' + wrapper + '[' + typ + ']')
            self.lines.append(name + ' = TypedDict(\n    ' + repr(name) + ',\n    {\n' + ''.join('        ' + field + ',\n' for field in fields) + '    },\n    total=False,\n)\n')
            value = name
        elif schema.get('type')=='object':
            extra = schema.get('additionalProperties')
            value = 'dict[str, ' + (self.type(extra,hint+'Item') if isinstance(extra,dict) else 'object') + ']'
        elif schema.get('type')=='array':
            value = 'list[' + self.type(schema.get('items',{}),hint+'Item') + ']'
        else:
            value = {'string':'str','integer':'int','number':'float','boolean':'bool','null':'None'}.get(schema.get('type'),'object')
        meta = {key:val for key,val in schema.items() if key not in ('type','properties','required','items','anyOf','oneOf','additionalProperties','enum')}
        # Preserve constraints and descriptions in the Python source of truth.
        if 'enum' in schema and not value.startswith('Literal['):
            meta['enum'] = schema['enum']
        if 'properties' in schema:
            meta['additionalProperties'] = schema.get('additionalProperties', True)
        if meta:
            value = 'Annotated[' + value + ', ' + repr(meta) + ']'
        return value

    def alias(self, name, schema):
        value = self.type(schema, name)
        self.lines.append(name + ': TypeAlias = ' + value + '\n')

    def source(self):
        return '\n'.join(self.lines)
