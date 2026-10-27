"""Portable third-party packages. Archives are staged before publication."""
import ast
import io
import json
import os
import re
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

from .components import ALIASES, builtin

MAX_ARCHIVE = 50 * 1024 * 1024
MAX_EXPANDED = 150 * 1024 * 1024
IGNORED = {'__pycache__', '.git', '.venv', 'node_modules', '.DS_Store', '.env'}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,40}', value) or builtin(value) or value in ALIASES:
        raise ValueError('第三方插件 ID 无效或与系统能力重名')
    return value


def program_path(root, name):
    identifier(name)
    folder, file = root / 'plugins' / name, root / 'plugins' / (name + '.py')
    if folder.is_symlink() or file.is_symlink():
        raise ValueError('插件程序不能是符号链接')
    if folder.is_dir() and (folder / '__init__.py').is_file():
        return folder
    if file.is_file():
        return file
    raise ValueError('第三方插件不存在')


def owned_state(store, name):
    return {row['key']: json.loads(row['value']) for row in store.rows(
        "SELECT key,value FROM kv WHERE substr(key,1,?)=?", (len(name) + 1, name + ':'))}


def add_tree(archive, folder, prefix):
    for file in sorted(folder.rglob('*')):
        relative = file.relative_to(folder)
        if file.is_file() and not file.is_symlink() and not any(p in IGNORED for p in relative.parts):
            archive.write(file, (PurePosixPath(prefix) / relative.as_posix()).as_posix())


def export_package(config, store, name, include_data=False):
    name = identifier(name)
    program = program_path(config.root, name)
    temp = config.root / 'temp' / 'plugin-exports'
    temp.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=name + '-', suffix='.zip', dir=temp)
    os.close(fd)
    output = Path(filename)
    try:
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('sakubot-plugin.json', json.dumps({'format': 'sakubot-plugin', 'version': 1,
                'id': name, 'state_included': include_data}, ensure_ascii=False))
            if program.is_dir():
                add_tree(archive, program, 'plugin')
            else:
                archive.write(program, 'plugin/__init__.py')
                metadata = program.with_suffix('.json')
                if metadata.is_file():
                    archive.write(metadata, 'plugin/plugin.json')
                else:
                    archive.writestr('plugin/plugin.json', json.dumps({'name': name, 'label': name}))
            if include_data:
                folder = config.root / 'plugin_data' / name
                if folder.is_dir() and not folder.is_symlink():
                    add_tree(archive, folder, 'plugin_data')
                archive.writestr('state.json', json.dumps(owned_state(store, name), ensure_ascii=False))
        with zipfile.ZipFile(output) as archive:
            if len(archive.infolist()) > 5000 or sum(item.file_size for item in archive.infolist()) > MAX_EXPANDED or output.stat().st_size > MAX_ARCHIVE:
                raise ValueError('插件包超过导入大小限制，请减少数据后导出')
        return output
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def import_package(config, store, content, include_data=False):
    if len(content) > MAX_ARCHIVE:
        raise ValueError('插件包超过50 MiB')
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ValueError('请选择有效 ZIP 插件包') from None
    with archive:
        entries = archive.infolist()
        if len(entries) > 5000 or sum(item.file_size for item in entries) > MAX_EXPANDED:
            raise ValueError('插件包解压体积或文件数超限')
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            if '\\' in item.filename or path.is_absolute() or '..' in path.parts or ':' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('插件包包含无效路径或符号链接')
            if item.filename in seen:
                raise ValueError('插件包包含重复路径')
            seen.add(item.filename)
        if 'sakubot-plugin.json' in seen:
            meta = json.loads(archive.read('sakubot-plugin.json'))
            if not isinstance(meta, dict) or meta.get('format') != 'sakubot-plugin' or meta.get('version') != 1:
                raise ValueError('插件包版本不支持')
            name, prefix = identifier(meta.get('id')), 'plugin/'
            package_state = meta.get('state_included') is True
        else:
            # Also accept a normal plugin directory ZIP with plugin.json.
            candidates = [file for file in seen if file == 'plugin.json' or file.count('/') == 1 and file.endswith('/plugin.json')]
            if len(candidates) != 1:
                raise ValueError('插件包需要唯一的 plugin.json 和 __init__.py')
            manifest = candidates[0]
            manifest_data = json.loads(archive.read(manifest))
            if not isinstance(manifest_data, dict):
                raise ValueError('plugin.json 必须是对象')
            name = identifier(manifest_data.get('name'))
            prefix = manifest[:-len('plugin.json')]
            package_state = False
        destination = config.root / 'plugins' / name
        if destination.exists() or destination.is_symlink() or destination.with_suffix('.py').exists() or destination.with_suffix('.py').is_symlink():
            raise ValueError('同名插件已存在')
        if prefix + '__init__.py' not in seen:
            raise ValueError('插件包缺少 __init__.py')
        selected_state = include_data and package_state
        state = json.loads(archive.read('state.json')) if selected_state and 'state.json' in seen else {}
        if not isinstance(state, dict) or any(not key.startswith(name + ':') for key in state):
            raise ValueError('插件数据键不属于当前插件')
        staging_root = config.root / 'temp'
        staging_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging_root, prefix='plugin-import-') as tmp:
            staging = Path(tmp)
            program, data = staging / 'program', staging / 'data'
            program.mkdir()
            existing_data = config.root / 'plugin_data' / name
            if existing_data.is_symlink():
                raise ValueError('插件数据目录不能是符号链接')
            if selected_state and existing_data.is_dir():
                shutil.copytree(existing_data, data)
            for item in entries:
                if item.is_dir():
                    continue
                relative = None
                root = None
                if item.filename.startswith(prefix):
                    relative, root = item.filename[len(prefix):], program
                    # Flat packages only include code and assets, never import bundle state as code.
                    if not prefix and relative in ('state.json', 'sakubot-plugin.json'):
                        continue
                elif selected_state and item.filename.startswith('plugin_data/'):
                    relative, root = item.filename[len('plugin_data/'):], data
                if root is None or not relative or any(p in IGNORED for p in PurePosixPath(relative).parts):
                    continue
                file = root / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(archive.read(item))
                file.chmod(0o700 if item.external_attr >> 16 & 0o111 else 0o600)
            try:
                ast.parse((program / '__init__.py').read_text(encoding='utf-8-sig'))
            except (SyntaxError, UnicodeError):
                raise ValueError('插件入口不是有效 Python 文件') from None
            manifest = program / 'plugin.json'
            metadata = json.loads(manifest.read_text()) if manifest.is_file() else {'name': name, 'label': name}
            if not isinstance(metadata, dict) or metadata.get('name', name) != name:
                raise ValueError('插件 ID 与清单不一致')
            manifest.write_text(json.dumps({**metadata, 'name': name}, ensure_ascii=False, indent=2))
            # Preserve existing state outside data before explicitly replacing any imported state.
            backup = None
            if selected_state and (existing_data.exists() or owned_state(store, name)):
                backup = config.root.parent / 'backups' / ('plugin-import-' + name + '-' + str(time.time_ns()))
                backup.mkdir(parents=True, mode=0o700)
                if existing_data.exists():
                    shutil.copytree(existing_data, backup / 'plugin_data')
                (backup / 'state.json').write_text(json.dumps(owned_state(store, name), ensure_ascii=False))
            destination.parent.mkdir(parents=True, exist_ok=True)
            previous = staging / 'previous-data'
            data_published = False
            try:
                os.rename(program, destination)
                if selected_state and data.exists():
                    existing_data.parent.mkdir(parents=True, exist_ok=True)
                    if existing_data.exists():
                        os.rename(existing_data, previous)
                    os.rename(data, existing_data)
                    data_published = True
                with store.db:
                    if selected_state:
                        for key, value in state.items():
                            store.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))
            except BaseException:
                if destination.exists():
                    shutil.rmtree(destination)
                if data_published and existing_data.exists():
                    shutil.rmtree(existing_data)
                if previous.exists():
                    os.rename(previous, existing_data)
                raise
    store.log('info', name, 'plugin.imported', data={'state_included': selected_state})
    return {'name': name, 'enabled': False, 'state_imported': selected_state}
