"""Shared persistent files, with optimistic versions and one mutation boundary."""
import hashlib
import os
import shutil
import tempfile
import threading
from pathlib import Path, PurePosixPath

MAX_FILE = 20 * 1024 * 1024
MAX_EDITOR = 1024 * 1024


def safe_path(root, value, *, allow_root=True):
    if not isinstance(value, str) or len(value) > 2048 or '\x00' in value or '\\' in value:
        raise ValueError('文件路径无效')
    relative = PurePosixPath(value or '.')
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('路径必须位于工作目录内')
    root = Path(root).resolve()
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('不支持符号链接')
    path = path.resolve()
    if not path.is_relative_to(root) or (path == root and not allow_root):
        raise ValueError('不能操作根目录')
    return path


def file_version(path):
    if not path.exists():
        return ''
    stat = path.stat()
    return hashlib.sha256(f'{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}'.encode()).hexdigest()


def text_page(path, offset=0, limit=200):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('分页参数无效')
    if not path.is_file():
        raise ValueError('文件不存在')
    if path.stat().st_size > MAX_FILE:
        raise ValueError('文件超过 20 MiB')
    before = file_version(path)
    raw = path.read_bytes()
    if file_version(path) != before:
        raise RuntimeError('文件已变化，请重新读取')
    try:
        if b'\x00' in raw:
            raise UnicodeError()
        content = raw.decode('utf-8-sig')
    except UnicodeError:
        return {'version': before, 'size': len(raw), 'binary': True, 'content': '', 'has_more': False}
    lines = content.splitlines(keepends=True)
    selected, count = '', 0
    for line in lines[offset:offset + limit]:
        if len(selected) + len(line) > 60000:
            if not count:
                raise ValueError('单行内容过长，请下载文件')
            break
        selected += line
        count += 1
    return {'version': before, 'size': len(raw), 'binary': False, 'content': selected,
        'offset': offset, 'next_offset': offset + count, 'total_lines': len(lines), 'has_more': offset + count < len(lines)}


class Workspace:
    def __init__(self, root, store):
        self.root, self.store = Path(root).resolve(), store
        self.lock = threading.RLock()
        from .shell import Shell
        self.shell_runner = Shell(self)
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in ('notes', 'projects', 'artifacts', 'tmp'):
            target = safe_path(self.root, directory)
            if not target.exists():
                target.mkdir()
        guide = safe_path(self.root, 'AGENTS.md')
        if not guide.exists():
            self._atomic(guide, ('# 工作空间\n\n所有 Agent 共用此目录。\n'
                '- notes/：持续维护的资料。\n- projects/：按项目组织任务资料。\n'
                '- artifacts/：完成后的报告和导出文件。\n- tmp/：临时文件。\n'
                '修改现有文件前先读取；局部修改使用带原文的 edit 或 patch，按内容检查冲突。整文件覆盖和移动删除保留版本保护。使用 shell 时协调写入。\n'
                '文件不会随 Agent 重置删除。仅在需要时读取相关资料，不重复执行历史文件中的操作。\n').encode())

    def path(self, value='', *, allow_root=True):
        return safe_path(self.root, value, allow_root=allow_root)

    async def shell(self, command, cwd='', timeout=60):
        return await self.shell_runner.run(command, cwd, timeout)

    def _record(self, action, path):
        self.store.log('info', 'workspace', 'workspace.' + action, data={'path': str(path.relative_to(self.root))})

    def _entry(self, path):
        stat = path.lstat()
        kind = 'link' if path.is_symlink() else 'directory' if path.is_dir() else 'file'
        return {'name': path.name, 'path': path.relative_to(self.root).as_posix(), 'type': kind,
            'size': stat.st_size, 'modified': stat.st_mtime, 'version': '' if kind == 'link' else file_version(path)}

    def list(self, path='', offset=0, limit=100, query=''):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('分页参数无效')
        with self.lock:
            target = self.path(path)
            if not target.is_dir():
                raise ValueError('目录不存在')
            version = file_version(target)
            entries = [self._entry(item) for item in target.iterdir() if query.casefold() in item.name.casefold()]
            entries.sort(key=lambda row: (row['type'] != 'directory', row['name'].casefold()))
            if file_version(target) != version:
                raise RuntimeError('目录已变化，请重新列出该目录')
            return {'path': target.relative_to(self.root).as_posix(), 'version': version, 'items': entries[offset:offset + limit],
                'total': len(entries), 'offset': offset, 'has_more': offset + limit < len(entries)}

    def read(self, path, offset=0, limit=200):
        with self.lock:
            result = {'path': path, **text_page(self.path(path, allow_root=False), offset, limit)}
            result['numbered_content'] = '\n'.join(f'{offset + index + 1}: {line}'
                for index, line in enumerate(result['content'].splitlines()))
            return {'path': path, 'numbered_content': result['numbered_content'], **result}

    def document(self, path):
        with self.lock:
            target = self.path(path, allow_root=False)
            if not target.is_file():
                raise ValueError('文件不存在')
            result = self._entry(target)
            result.update(editable=False, binary=False, content='')
            if target.stat().st_size > MAX_EDITOR:
                return result
            raw = target.read_bytes()
            if file_version(target) != result['version']:
                raise RuntimeError('文件已变化，请重新读取')
            try:
                if b'\x00' in raw:
                    raise UnicodeError()
                result.update(content=raw.decode('utf-8'), editable=True)
            except UnicodeError:
                result['binary'] = True
            return result

    @staticmethod
    def _atomic(path, content):
        descriptor, name = tempfile.mkstemp(prefix='.sakubot-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _check(self, path, version):
        if not isinstance(version, str) or file_version(path) != version:
            if path.is_dir():
                raise RuntimeError('目录已变化，请重新列出该目录，使用返回的顶层 version 重试')
            raise RuntimeError('文件已变化，请重新读取后重试')

    def write_bytes(self, path, content, version=''):
        if not isinstance(content, bytes) or len(content) > MAX_FILE:
            raise ValueError('文件超过 20 MiB')
        with self.lock:
            target = self.path(path, allow_root=False)
            if target.exists() and not target.is_file():
                raise ValueError('目标不是文件')
            self._check(target, version)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._atomic(target, content)
            self._record('written', target)
            return self._entry(target)

    def write(self, path, content, version='', base_content=None):
        if not isinstance(content, str):
            raise ValueError('正文必须为文本')
        if base_content is not None:
            if not isinstance(base_content, str):
                raise ValueError('原正文必须为文本')
            with self.lock:
                document = self.document(path)
                if not document['editable'] or document['content'] != base_content:
                    raise RuntimeError('文件正文已变化，整文件覆盖冲突；请重新读取或改用局部 patch')
                return self.write_bytes(path, content.encode('utf-8'), document['version'])
        return self.write_bytes(path, content.encode('utf-8'), version)

    def edit(self, path, old, new, version=''):
        return self.patch(path, [{'old': old, 'new': new}], version)

    def patch(self, path, hunks, version=''):
        if not isinstance(hunks, list) or not 1 <= len(hunks) <= 100:
            raise ValueError('补丁应包含 1～100 个修改块')
        with self.lock:
            document = self.document(path)
            if not document['editable']:
                raise ValueError('文件不可编辑')
            content = document['content']
            changes = []
            for index, hunk in enumerate(hunks):
                if not isinstance(hunk, dict):
                    raise ValueError('补丁块无效')
                old, new, line = hunk.get('old'), hunk.get('new'), hunk.get('start_line')
                if not isinstance(old, str) or not old or not isinstance(new, str):
                    raise ValueError('补丁必须提供非空 old 原文和 new 正文；插入时包含相邻原文作为锚点')
                if line is not None and (type(line) is not int or line < 1):
                    raise ValueError('start_line 从 1 开始')
                start = content.find(old)
                if start < 0:
                    raise RuntimeError(f'补丁第 {index + 1} 块冲突：原文已变化或不存在，请重新读取相关位置')
                if content.find(old, start + 1) >= 0:
                    raise RuntimeError(f'补丁第 {index + 1} 块存在多处匹配，请增加上下文原文')
                actual_line = content.count('\n', 0, start) + 1
                changes.append((start, start + len(old), new, {
                    'hunk': index + 1, 'requested_line': line, 'matched_line': actual_line,
                    'shifted': line is not None and line != actual_line}))
            changes.sort(key=lambda row: row[0])
            if any(previous[1] > current[0] for previous, current in zip(changes, changes[1:])):
                raise ValueError('补丁修改块重叠，请合并为一个块')
            for start, end, new, _ in reversed(changes):
                content = content[:start] + new + content[end:]
            result = self.write(path, content, document['version'])
            return {**result, 'rebased': bool(version and version != document['version']),
                'hunks': [row[3] for row in changes]}

    def mkdir(self, path):
        with self.lock:
            target = self.path(path, allow_root=False)
            if target.exists():
                raise ValueError('目录或文件已存在')
            target.mkdir(parents=True, exist_ok=False)
            self._record('directory.created', target)
            return self._entry(target)

    def move(self, path, destination, version):
        with self.lock:
            source = self.path(path, allow_root=False)
            target = self.path(destination, allow_root=False)
            if not source.exists():
                raise ValueError('文件不存在')
            self._check(source, version)
            if target.exists():
                raise ValueError('目标已存在')
            if target.is_relative_to(source):
                raise ValueError('不能移动到自身目录')
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            self._record('moved', target)
            return self._entry(target)

    def remove(self, path, version, recursive=False):
        with self.lock:
            target = self.path(path, allow_root=False)
            if not target.exists():
                raise ValueError('文件不存在')
            self._check(target, version)
            if target.is_dir():
                if recursive:
                    shutil.rmtree(target)
                else:
                    if any(target.iterdir()):
                        raise ValueError('目录非空，请选择递归删除')
                    target.rmdir()
            else:
                target.unlink()
            self._record('removed', target)
            return {'removed': path}
