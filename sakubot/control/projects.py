"""Editable development trees, static validation and reversible publication."""
import ast
import asyncio
import hashlib
import importlib.metadata
import json
import os
import shutil
import time
import uuid
from pathlib import Path

from ..plugin_packages import identifier, program_path
from ..automation.repository import atomic
from .plugins import tree_version

SDK = Path('/app/plugin-sdk')


class Projects:
    def __init__(self, control):
        self.control, self.runtime = control, control.runtime
        self.root = self.runtime.config.root / 'plugin_projects'
        self.revisions = self.runtime.config.root / 'plugin_revisions'
        self.root.mkdir(parents=True, exist_ok=True)
        self.revisions.mkdir(parents=True, exist_ok=True)

    def path(self, name):
        identifier(name)
        if self.root.is_symlink():
            raise ValueError('开发目录不能是符号链接')
        path = self.root / name
        if path.is_symlink():
            raise ValueError('开发项目不能是符号链接')
        return path

    def file(self, name, relative):
        root = self.path(name)
        if not root.is_dir():
            raise ValueError('开发项目不存在')
        if not isinstance(relative, str) or not relative or '\\' in relative:
            raise ValueError('项目文件路径无效')
        requested = Path(relative)
        if requested.is_absolute() or '..' in requested.parts or any(part in ('.git','node_modules','__pycache__') for part in requested.parts):
            raise ValueError('项目文件路径无效')
        current = root
        for part in requested.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError('项目文件不能是符号链接')
        return current

    def list(self):
        return [{'id': path.name, 'version': tree_version(path)} for path in sorted(self.root.iterdir())
                if path.is_dir() and not path.is_symlink() and (path/'__init__.py').is_file()]

    def inspect(self, name):
        root = self.path(name)
        if not root.is_dir():
            raise ValueError('开发项目不存在')
        files = [str(path.relative_to(root)) for path in sorted(root.rglob('*')) if path.is_file()
                 and not any(part in ('node_modules','__pycache__','.git') for part in path.relative_to(root).parts)]
        return {'id': name, 'version': tree_version(root), 'files': files[:2000]}

    def create(self, name, label='', with_page=True):
        root = self.path(name)
        if root.exists():
            raise ValueError('同名开发项目已存在')
        label = label or name
        if not isinstance(label,str) or not 1 <= len(label) <= 100:
            raise ValueError('名称须为 1～100 字')
        root.mkdir()
        manifest = {'name':name,'label':label,'version':'0.1.0','icon':'plugins'}
        atomic(root/'plugin.json', json.dumps(manifest,ensure_ascii=False,indent=2))
        setup = "        self.function(self.read, name='" + name + "_read')\n"
        if with_page:
            setup += "        self.management(" + repr(label) + ", [settings_section([field('value', '内容')], id='entry', label='内容')], self.view, self.manage)\n"
        code = ("from sakubot.plugin import Plugin\nfrom sakubot.plugin_support import field, settings_section\n\n\n"
                "class Extension(Plugin):\n    name = " + repr(name) + "\n\n    def setup(self):\n" + setup +
                "\n    async def read(self):\n        \"\"\"读取插件内容。\"\"\"\n        return self.state.get('entry', {'value': ''})\n"
                "\n    def view(self):\n        return {'data': {'entry': self.state.get('entry', {'value': ''})}}\n"
                "\n    async def manage(self, data):\n        value = data['value']['value']\n        if not isinstance(value, str) or len(value) > 10000:\n            raise ValueError('内容须为不超过 10000 字的文本')\n        self.state.set('entry', {'value': value})\n        return {'saved': True}\n")
        atomic(root/'__init__.py', code)
        if with_page:
            web = root/'web'
            atomic(web/'index.html', '<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head><body><div id="app"></div><script type="module" src="/src/main.ts"></script></body></html>')
            atomic(web/'src/main.ts', "import { mountPlugin } from '@sakubot/ui'\nimport App from './App.vue'\nmountPlugin(App)\n")
            atomic(web/'src/App.vue', "<script setup lang=\"ts\">\nimport { PluginWorkbench } from '@sakubot/ui'\n</script>\n<template><PluginWorkbench /></template>\n")
        return self.inspect(name)

    def checkout(self, name):
        target = self.path(name)
        if target.exists():
            raise ValueError('开发项目已存在，不覆盖本地修改')
        source = program_path(self.runtime.config.root, name)
        if source.is_file():
            target.mkdir()
            shutil.copy2(source,target/'__init__.py')
            atomic(target/'plugin.json',json.dumps({'name':name,'label':name,'version':'0.1.0'}))
        else:
            tree_version(source)
            shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','node_modules','.git'))
        return self.inspect(name)

    def read(self, name, relative):
        file = self.file(name, relative)
        if not file.is_file() or file.stat().st_size > 500000:
            raise ValueError('文件不存在或超过 500 KB')
        raw = file.read_bytes()
        try:
            content=raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('仅可编辑 UTF-8 文本文件') from None
        return {'path':relative,'content':content,'file_version':hashlib.sha256(raw).hexdigest()}

    def write(self, name, relative, content, expected_version=None):
        file = self.file(name, relative)
        if not isinstance(content,str) or len(content.encode()) > 500000:
            raise ValueError('文件须为不超过 500 KB 的文本')
        if file.exists() and (not file.is_file() or expected_version != hashlib.sha256(file.read_bytes()).hexdigest()):
            raise ValueError('文件已变化，请重新读取并携带 file_version')
        atomic(file,content)
        return self.read(name,relative)

    def source_version(self, name):
        web=self.path(name)/'web'
        digest=hashlib.sha256()
        if web.is_dir():
            for file in sorted(web.rglob('*')):
                relative=file.relative_to(web)
                if any(part in ('dist','node_modules','__pycache__') for part in relative.parts): continue
                if file.is_file():
                    digest.update(str(relative).encode()); digest.update(file.read_bytes())
        return digest.hexdigest()

    def check(self, name):
        root = self.path(name)
        version = tree_version(root)
        metadata = json.loads((root/'plugin.json').read_text())
        if not isinstance(metadata,dict) or metadata.get('name') != name or not (root/'__init__.py').is_file():
            raise ValueError('插件清单与入口无效')
        total = 0
        for file in root.rglob('*'):
            if not file.is_file():
                continue
            total += file.stat().st_size
            if total > 150 * 1024 * 1024:
                raise ValueError('开发项目超过 150 MiB')
            if file.suffix == '.py':
                try:
                    ast.parse(file.read_text(encoding='utf-8-sig'), filename=str(file.relative_to(root)))
                except SyntaxError as exc:
                    raise ValueError(f'Python 语法错误 {file.relative_to(root)}:{exc.lineno}：{exc.msg}') from None
            elif file.suffix == '.json' and 'web/dist/' not in str(file):
                try:
                    json.loads(file.read_text())
                except json.JSONDecodeError as exc:
                    raise ValueError(f'JSON 格式错误 {file.relative_to(root)}:{exc.lineno}:{exc.colno}：{exc.msg}') from None
        dependencies = []
        requirements = root/'requirements.txt'
        if requirements.is_file():
            from packaging.requirements import Requirement, InvalidRequirement
            for line in requirements.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith('#'): continue
                try:
                    requirement=Requirement(line)
                except InvalidRequirement:
                    raise ValueError('依赖须为 PyPI 包名和版本声明') from None
                if requirement.url:
                    raise ValueError('依赖不支持外部 URL')
                applicable=not requirement.marker or requirement.marker.evaluate()
                try:
                    installed=importlib.metadata.version(requirement.name)
                except importlib.metadata.PackageNotFoundError:
                    installed=''
                satisfied=not applicable or bool(installed and requirement.specifier.contains(installed,prereleases=True))
                dependencies.append({'requirement':line,'installed':installed,'satisfied':satisfied,'applicable':applicable})
        return {'id':name,'version':version,'python_syntax':'valid','dependencies':dependencies,
                'page_build_required':(root/'web/index.html').is_file() and (not (root/'web/dist/index.html').is_file() or self.runtime.store.kv_get('control:project-build:'+name) != self.source_version(name))}

    async def build(self, name, operation_id):
        self.check(name)
        if not (self.path(name)/'web/index.html').is_file():
            return self.check(name)
        if not (SDK/'build-page.mjs').is_file():
            raise ValueError('当前安装未包含前端开发 SDK，请更新运行镜像')
        source_version=self.source_version(name)
        process = await asyncio.create_subprocess_exec('node',str(SDK/'build-page.mjs'),str(self.path(name)/'web'),
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,start_new_session=os.name!='nt')
        try:
            async with asyncio.timeout(180):
                while chunk := await process.stdout.read(4096):
                    self.control.operations.log(operation_id,chunk.decode(errors='replace'))
                if await process.wait():
                    raise RuntimeError('页面构建失败，请查看操作日志')
        except TimeoutError:
            raise RuntimeError('页面构建超过 180 秒，请检查构建日志') from None
        finally:
            if process.returncode is None:
                if os.name == 'nt': process.kill()
                else:
                    import signal
                    try: os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                await process.wait()
        if source_version != self.source_version(name):
            raise ValueError('构建期间源码已变化，请重新构建')
        self.runtime.store.kv_set('control:project-build:'+name,source_version)
        return self.check(name)

    def save_revision(self, name, path):
        tree_version(path)
        folder = self.revisions/name/(str(time.time_ns()) + '-' + uuid.uuid4().hex[:6])
        folder.mkdir(parents=True)
        if path.is_dir(): shutil.copytree(path,folder/'program',ignore=shutil.ignore_patterns('__pycache__','node_modules','.git'))
        else:
            (folder/'program').mkdir()
            shutil.copy2(path,folder/'program/__init__.py')
            if path.with_suffix('.json').is_file(): shutil.copy2(path.with_suffix('.json'),folder/'program/plugin.json')
        atomic(folder/'metadata.json', json.dumps({'single_file':path.is_file()}))
        return folder.name

    def restore_last(self, name):
        folder = self.revisions/name
        versions = sorted(folder.iterdir(),reverse=True) if folder.is_dir() else []
        if not versions: return False
        self.restore(name,versions[0].name)
        return True

    def restore(self, name, version):
        identifier(name)
        if not isinstance(version,str) or not version or any(c not in '0123456789abcdef-' for c in version):
            raise ValueError('版本无效')
        source = self.revisions/name/version/'program'
        tree_version(source)
        if not source.is_dir() or self.revisions.is_symlink() or (self.revisions/name).is_symlink() or source.parent.is_symlink(): raise ValueError('版本不存在或目录无效')
        destination = self.runtime.config.root/'plugins'/name
        staging = self.runtime.config.root/'plugins'/('.publish-'+uuid.uuid4().hex)
        shutil.copytree(source,staging)
        if destination.is_symlink() or destination.with_suffix('.py').is_symlink(): raise ValueError('插件程序不能是符号链接')
        if destination.exists(): shutil.rmtree(destination)
        destination.with_suffix('.py').unlink(missing_ok=True)
        destination.with_suffix('.json').unlink(missing_ok=True)
        os.replace(staging,destination)

    def versions(self,name):
        identifier(name)
        folder=self.revisions/name
        return [{'id':p.name} for p in sorted(folder.iterdir(),reverse=True)] if folder.is_dir() else []

    async def publish(self,name,expected_version,*,enable=True,force=False,rollback=''):
        async with self.control.lock:
            if not rollback:
                checked=self.check(name)
                if checked['version'] != expected_version: raise ValueError('开发项目已变化，请重新检查后发布')
                if checked['page_build_required']: raise ValueError('请先构建插件页面')
                if any(not row['satisfied'] for row in checked['dependencies']): raise ValueError('插件依赖尚未安装，请先查看依赖清单')
            identifier(name)
            await self.control.plugins.idle(name,force)
            if not rollback and tree_version(self.path(name)) != expected_version:
                raise ValueError('等待期间开发项目已变化，请重新检查后发布')
            loaded=self.runtime.registry.loaded(name)
            try: old=program_path(self.runtime.config.root,name)
            except ValueError: old=None
            previous=self.save_revision(name,old) if old else ''
            await self.runtime.registry.disable(name)
            try:
                if rollback: self.restore(name,rollback)
                else:
                    source=self.path(name)
                    stage=self.runtime.config.root/'plugins'/('.publish-'+uuid.uuid4().hex)
                    shutil.copytree(source,stage,ignore=shutil.ignore_patterns('__pycache__','node_modules','.git'))
                    dest=self.runtime.config.root/'plugins'/name
                    if dest.exists(): shutil.rmtree(dest)
                    dest.with_suffix('.py').unlink(missing_ok=True)
                    dest.with_suffix('.json').unlink(missing_ok=True)
                    os.replace(stage,dest)
                await self.control.plugins._toggle(name,enable or loaded,force=force)
            except BaseException:
                await self.runtime.registry.disable(name)
                if previous: self.restore(name,previous)
                else:
                    dest=self.runtime.config.root/'plugins'/name
                    if dest.exists(): shutil.rmtree(dest)
                if loaded: await self.runtime.registry.enable(name,start=self.runtime.sources_started)
                raise
            return {'name':name,'published':True,'enabled':enable or loaded,'previous_version':previous}
