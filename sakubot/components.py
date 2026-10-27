"""System capability ownership and compatibility for consolidated components."""
import re
from pathlib import Path

SYSTEM_ROOT = Path(__file__).parent / 'system'
BUILTIN_ROOT = Path(__file__).parent / 'plugins'
ALIASES = {'pdf': 'office', 'documents': 'office', 'spreadsheets': 'office'}


def system_ids():
    return [p.name for p in sorted(SYSTEM_ROOT.iterdir()) if p.is_dir() and (p / '__init__.py').is_file()]


def canonical(identifier):
    return ALIASES.get(identifier, identifier)


def required(identifier):
    return bool(re.fullmatch(r'[a-z][a-z0-9_]{0,40}', identifier)) and (SYSTEM_ROOT / identifier / '__init__.py').is_file()


def builtin(identifier):
    return required(identifier) or (BUILTIN_ROOT / identifier / '__init__.py').is_file()


def optional_ids(identifiers):
    return list(dict.fromkeys(canonical(name) for name in identifiers if not required(canonical(name))))


def visible_ids(identifiers):
    return None if identifiers is None else optional_ids(identifiers)


def migrate_saved(store):
    personas = store.kv_get('personas', {})
    changed = False
    for row in personas.values():
        previous = row.get('visible_plugins')
        current = visible_ids(previous)
        if previous != current:
            row['visible_plugins'] = current
            changed = True
    if changed:
        store.kv_set('personas', personas)
    members = store.kv_get('team:members', [])
    changed = False
    for member in members:
        persona = member.get('persona')
        if isinstance(persona, dict):
            previous = persona.get('visible_plugins')
            current = visible_ids(previous)
            if previous != current:
                persona['visible_plugins'] = current
                changed = True
    if changed:
        store.kv_set('team:members', members)
