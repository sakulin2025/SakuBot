"""Read-only skill discovery and plugin-owned declarations."""
import hashlib
import re
import uuid
from pathlib import Path

import yaml

from .workspace import safe_path, text_page
from .store import encode
from .components import canonical


class Skills:
    def __init__(self, runtime):
        self.runtime = runtime
        self.root = runtime.config.root / 'skills'
        self.root.mkdir(parents=True, exist_ok=True)
        self.declarations = {}
        self.errors = []

    def declare(self, owner, identifier, directory):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identifier):
            raise ValueError('技能 ID 无效')
        directory = Path(directory).resolve()
        self.metadata(owner, identifier, directory)
        self.declarations[owner + '.' + identifier] = (owner, identifier, directory)
        self.runtime.registry.revision = uuid.uuid4().hex
        return owner + '.' + identifier

    def discover(self, owner, directory):
        root = Path(directory) / 'skills'
        if not root.is_dir():
            return
        for item in sorted(root.iterdir()):
            if owner + '.' + item.name in self.declarations:
                continue
            if item.is_dir() and not item.is_symlink() and (item / 'SKILL.md').is_file():
                try:
                    self.declare(owner, item.name, item)
                except (ValueError, OSError, UnicodeError, yaml.YAMLError):
                    self.runtime.store.log('warning', owner, 'skill.invalid', data={'skill': item.name})

    def remove_owner(self, owner):
        self.declarations = {key: value for key, value in self.declarations.items() if value[0] != owner}

    @staticmethod
    def metadata(owner, identifier, directory):
        path = safe_path(directory, 'SKILL.md', allow_root=False)
        if not path.is_file() or path.stat().st_size > 128 * 1024:
            raise ValueError('技能缺少 SKILL.md 或文件过大')
        content = path.read_text(encoding='utf-8-sig')
        parts = re.split(r'^---\s*$', content, maxsplit=2, flags=re.M)
        if len(parts) != 3 or parts[0].strip():
            raise ValueError('SKILL.md 需要 YAML 元数据')
        data = yaml.safe_load(parts[1])
        if not isinstance(data, dict):
            raise ValueError('技能元数据无效')
        name, description = data.get('name'), data.get('description')
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or not isinstance(description, str) or not description.strip() or len(description) > 2000:
            raise ValueError('技能需要 name 和 description')
        return {'id': (owner or 'local') + '.' + identifier, 'name': name.strip(), 'description': description.strip(),
            'plugin_id': owner, 'source': owner or 'local', 'version': hashlib.sha256(content.encode()).hexdigest(),
            'content': content, 'body': parts[2].lstrip()}

    def catalog(self, visible=None):
        records = [entry for entry in self.declarations.values()
            if self.runtime.registry.loaded(entry[0]) and (visible is None or entry[0] in visible)]
        if self.root.is_dir():
            for directory in sorted(self.root.iterdir()):
                if directory.is_dir() and not directory.is_symlink() and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', directory.name) and (directory / 'SKILL.md').is_file():
                    records.append(('', directory.name, directory))
        result, errors = [], []
        for owner, identifier, directory in records:
            try:
                row = self.metadata(owner, identifier, directory)
                result.append({key: value for key, value in row.items() if key not in ('content', 'body')})
            except (OSError, UnicodeError, ValueError, yaml.YAMLError):
                errors.append({'id': (owner or 'local') + '.' + identifier, 'error': 'SKILL.md 无效'})
        self.errors = errors
        return sorted(result, key=lambda row: row['id'])

    def _record(self, identifier, visible=None):
        owner, dot, name = identifier.partition(".")
        identifier = canonical(owner) + dot + name
        record = next((row for row in self.catalog(visible) if row['id'] == identifier), None)
        if not record:
            raise ValueError('技能不存在或当前人格不可见')
        directory = self.declarations[identifier][2] if record['plugin_id'] else safe_path(self.root, identifier[len('local.'):], allow_root=False)
        return self.metadata(record['plugin_id'], identifier.split('.', 1)[1], directory), directory

    def read(self, identifier, visible=None):
        record, directory = self._record(identifier, visible)
        files = []
        for path in directory.rglob('*'):
            if path.is_file() and not path.is_symlink():
                try:
                    relative = path.relative_to(directory).as_posix()
                    safe_path(directory, relative, allow_root=False)
                    if relative != 'SKILL.md':
                        files.append(relative)
                except ValueError:
                    continue
            if len(files) >= 500:
                break
        return {**record, 'directory': str(directory), 'files': sorted(files)}

    def read_file(self, identifier, path, offset=0, limit=200, visible=None):
        record, directory = self._record(identifier, visible)
        return {'id': record['id'], 'path': path, **text_page(safe_path(directory, path, allow_root=False), offset, limit)}

    def index(self, visible):
        catalog = self.catalog(visible)
        result, size = [], 0
        for row in catalog:
            item = {key: row[key] for key in ('id', 'name', 'description')}
            item['description'] = item['description'][:400]
            cost = len(encode(item))
            if size + cost > 16000:
                break
            result.append(item)
            size += cost
        return encode({'items': result, 'total': len(catalog)})
