"""Plugin lifecycle transactions without HTTP or Agent-specific dependencies."""
import asyncio
import hashlib
import json
import shutil
from pathlib import Path

from ..components import canonical, required
from ..plugin_packages import export_package, import_package, program_path


def tree_version(path):
    if not path.exists():
        raise ValueError('插件程序不存在')
    digest = hashlib.sha256()
    total = 0
    files = [path] if path.is_file() else sorted(path.rglob('*'))
    for file in files:
        if file.is_symlink():
            raise ValueError('插件程序不能包含符号链接')
        if not file.is_file() or any(part in ('__pycache__', '.git', 'node_modules') for part in file.relative_to(path.parent if path.is_file() else path).parts):
            continue
        digest.update(str(file.relative_to(path.parent if path.is_file() else path)).encode())
        total += file.stat().st_size
        if total > 150 * 1024 * 1024:
            raise ValueError('插件程序超过 150 MiB')
        with file.open('rb') as source:
            while chunk := source.read(512 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


class Plugins:
    def __init__(self, control):
        self.control, self.runtime = control, control.runtime

    def scan(self):
        rows = self.runtime.registry.installed_catalog()
        current = {}
        for row in rows:
            try:
                path = self.path(row['name'])
                row['version_hash'] = tree_version(path)
            except (OSError, ValueError):
                row['version_hash'] = ''
            current[row['name']] = row['version_hash']
        previous = self.runtime.store.kv_get('control:plugin_inventory', {})
        self.runtime.store.kv_set('control:plugin_inventory', current)
        return {'plugins': rows, 'added': [key for key in current if key not in previous],
                'changed': [key for key in current if key in previous and current[key] != previous[key]],
                'removed': [key for key in previous if key not in current]}

    def path(self, identifier):
        from ..components import SYSTEM_ROOT, BUILTIN_ROOT
        if required(identifier):
            return SYSTEM_ROOT / identifier
        if (BUILTIN_ROOT / identifier / '__init__.py').is_file():
            return BUILTIN_ROOT / identifier
        return program_path(self.runtime.config.root, identifier)

    def busy(self, identifier):
        registry = self.runtime.registry
        tools = [task for task in registry.inflight.get(identifier, set()) if not task.done()]
        agents = [task for instance in self.runtime.agents.instances.values()
                  for task, owner in instance.tasks.items()
                  if not task.done() and (owner == identifier or instance.id.startswith(identifier + ':'))]
        return len(set(tools + agents))

    async def idle(self, identifier, force=False):
        if force:
            return
        deadline = asyncio.get_running_loop().time() + 300
        while self.busy(identifier):
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError('插件仍有任务运行，未执行变更；可等待结束或显式强制操作')
            await asyncio.sleep(.25)

    async def toggle(self, identifier, enabled, *, force=False):
        async with self.control.lock:
            return await self._toggle(identifier, enabled, force=force)

    async def _toggle(self, identifier, enabled, *, force=False):
        identifier = canonical(identifier)
        if type(enabled) is not bool:
            raise ValueError('插件状态无效')
        if required(identifier):
            if not enabled:
                raise ValueError('基础能力不能停用')
            return {'name': identifier, 'enabled': True}
        if not any(row['name'] == identifier for row in self.runtime.registry.installed_catalog()):
            raise ValueError('未发现插件，请先扫描或导入')
        present = self.runtime.registry.loaded(identifier)
        settings = self.runtime.config.settings.model_copy(deep=True)
        if not enabled:
            await self.idle(identifier, force)
        try:
            if enabled:
                await self.runtime.registry.enable(identifier, start=self.runtime.sources_started)
                if identifier not in settings.plugins:
                    settings.plugins.append(identifier)
            else:
                await self.runtime.registry.disable(identifier)
                settings.plugins = [name for name in settings.plugins if name != identifier]
            self.runtime.config.save(settings)
            self.runtime.model.settings = settings
        except BaseException:
            if enabled and not present:
                await self.runtime.registry.disable(identifier)
            elif not enabled and present:
                await self.runtime.registry.enable(identifier, start=self.runtime.sources_started)
            raise
        return {'name': identifier, 'enabled': enabled}

    async def reload(self, identifier, *, force=False):
        async with self.control.lock:
            if required(identifier):
                raise ValueError('基础能力由系统管理；需要时重启系统')
            if not self.runtime.registry.loaded(identifier):
                raise ValueError('插件未启用')
            await self.idle(identifier, force)
            try:
                await self.runtime.registry.reload(identifier)
            except Exception:
                # A published revision may be recoverable even after a manual file edit.
                restored = self.control.projects.restore_last(identifier)
                if restored:
                    await self.runtime.registry.enable(identifier, start=self.runtime.sources_started)
                self.runtime.registry.errors[identifier] = '重载失败' + ('，已恢复上一版' if restored else '，请修复代码后重试')
                raise RuntimeError(self.runtime.registry.errors[identifier]) from None
            return {'name': identifier, 'reloaded': True}

    async def delete(self, identifier, *, purge=False, confirm=False, force=False):
        if confirm is not True:
            raise ValueError('请确认删除插件')
        async with self.control.lock:
            program = program_path(self.runtime.config.root, identifier)
            await self.idle(identifier, force)
            await self._toggle(identifier, False, force=force)
            if program.is_dir():
                shutil.rmtree(program)
            else:
                program.unlink()
                program.with_suffix('.json').unlink(missing_ok=True)
            store = self.runtime.store
            preinstalled = store.kv_get('preinstalled:state', {})
            if identifier in preinstalled.get('ids', []):
                preinstalled['ids'].remove(identifier)
                store.kv_set('preinstalled:state', preinstalled)
            if purge:
                folder = self.runtime.config.root / 'plugin_data' / identifier
                if folder.is_symlink():
                    folder.unlink()
                elif folder.exists():
                    shutil.rmtree(folder)
                for prefix in (identifier + ':', 'agent:history:' + identifier + ':', 'agent:pending:' + identifier + ':'):
                    store.execute('DELETE FROM kv WHERE substr(key,1,?)=?', (len(prefix), prefix))
            store.execute("UPDATE events SET status='cancelled',meta=json_set(meta,'$.exclude_context',json('true')) WHERE source=? AND status='pending' AND kind='wake'", (identifier,))
            self.runtime.registry.errors.pop(identifier, None)
            store.log('warning', identifier, 'plugin.deleted', data={'purge': purge})
            return {'deleted': identifier, 'data_removed': purge}

    async def import_archive(self, path, include_data=False):
        async with self.control.lock:
            from ..plugin_packages import MAX_ARCHIVE
            if not Path(path).is_file() or Path(path).stat().st_size > MAX_ARCHIVE:
                raise ValueError('插件包不存在或超过 50 MiB')
            content = Path(path).read_bytes()
            return import_package(self.runtime.config, self.runtime.store, content, include_data)

    async def export_archive(self, identifier, include_data=False):
        async with self.control.lock:
            path = export_package(self.runtime.config, self.runtime.store, identifier, include_data)
            return path
