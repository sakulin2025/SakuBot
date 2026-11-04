"""Install bundled third-party plugins once into a fresh data volume."""
import io
import json
import zipfile
from pathlib import Path

from .plugin_packages import add_tree, import_package, program_path

IDS = ('ssh_devices', 'qweather', 'deepseek_balance', 'alist_manage', 'ha_control', 'minecraft_status')
PACKAGES = Path(__file__).resolve().parent.parent / 'preinstalled'
KEY = 'preinstalled:state'


def bootstrap(config, store):
    if not PACKAGES.is_dir():
        return
    state = store.kv_get(KEY)
    if state is None:
        ids = []
        for name in IDS:
            try:
                program_path(config.root, name)
                ids.append(name)
            except ValueError:
                pass
        state = {'status': 'installing' if config.fresh_install else 'complete', 'ids': ids}
        store.kv_set(KEY, state)
    if state.get('status') != 'installing':
        # Label newly bundled plugins already installed on an existing deployment,
        # without installing absent plugins or restoring deliberately removed ones.
        changed = False
        for name in IDS:
            if name in state.get('ids', []):
                continue
            try:
                program_path(config.root, name)
            except ValueError:
                continue
            state.setdefault('ids', []).append(name)
            changed = True
        if changed:
            store.kv_set(KEY, state)
        return
    for name in IDS:
        if name in state['ids']:
            continue
        try:
            program_path(config.root, name)
        except ValueError:
            directory = PACKAGES / name
            if not (directory / '__init__.py').is_file() or not (directory / 'web' / 'dist' / 'index.html').is_file():
                raise RuntimeError('预装插件包不完整：' + name)
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('sakubot-plugin.json', json.dumps({'format': 'sakubot-plugin', 'version': 1, 'id': name, 'state_included': False}))
                add_tree(archive, directory, 'plugin')
            import_package(config, store, data.getvalue())
        state['ids'].append(name)
        store.kv_set(KEY, state)
    state['status'] = 'complete'
    store.kv_set(KEY, state)
