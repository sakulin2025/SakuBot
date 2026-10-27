"""Shared local file/conversion helpers; capabilities are declared by plugins."""
import asyncio
import json
import os
import shutil
import signal
import tempfile
import uuid
from pathlib import Path


_CONVERSIONS = asyncio.Semaphore(2)


def source(plugin, path, suffixes):
    result = plugin.workspace.path(path, allow_root=False)
    if not result.is_file() or result.suffix.lower() not in suffixes:
        raise ValueError('文件不存在或格式不支持：' + ', '.join(sorted(suffixes)))
    if result.stat().st_size > 50 * 1024 * 1024:
        raise ValueError('文件超过50 MiB，请使用工作空间脚本分批处理')
    return result


def destination(plugin, path, suffixes):
    result = plugin.workspace.path(path, allow_root=False)
    if result.suffix.lower() not in suffixes:
        raise ValueError('输出格式需为：' + ', '.join(sorted(suffixes)))
    if result.exists():
        raise ValueError('输出文件已存在，请选择新文件名以保留原件')
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def save_new(path, writer):
    # Write a complete temporary file, then atomically claim a new output name.
    with tempfile.TemporaryDirectory(dir=path.parent, prefix='.office-') as folder:
        staging = Path(folder) / path.name
        writer(staging)
        os.link(staging, path)


def result(plugin, path):
    data = {'path': path.relative_to(plugin.workspace.root).as_posix(), 'bytes': path.stat().st_size}
    if path.stat().st_size <= 20 * 1024 * 1024:
        data['artifact'] = plugin.artifact(path)
    return data


def bounded(data, limit=18000):
    if len(json.dumps(data, ensure_ascii=False, default=str)) > limit:
        raise ValueError('读取结果过长，请缩小页数、行数或范围后重新读取')
    return data


async def command(args, timeout=120, env=None):
    proc = await asyncio.create_subprocess_exec(*map(str, args), stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT, start_new_session=True, env=env)
    try:
        async with asyncio.timeout(timeout):
            output, _ = await proc.communicate()
    except BaseException:
        if proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
        raise
    if proc.returncode:
        raise ValueError('文档处理失败，退出码 ' + str(proc.returncode) + '；请检查文件格式、加密状态或字体')
    return output.decode(errors='replace')


async def convert(plugin, path, output, format):
    async with _CONVERSIONS:
        with tempfile.TemporaryDirectory(prefix='sakubot-office-') as folder:
            root = Path(folder)
            local_input = root / 'source' / path.name
            local_input.parent.mkdir()
            shutil.copyfile(path, local_input)
            profile = root / 'profile'
            (profile / 'user').mkdir(parents=True)
            (profile / 'user/registrymodifications.xcu').write_text('''<?xml version="1.0"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="LinkUpdateMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>''')
            target = root / 'converted'
            target.mkdir()
            await command(['libreoffice', '-env:UserInstallation=' + profile.as_uri(), '--headless', '--nologo',
                '--nodefault', '--nofirststartwizard', '--convert-to', format, '--outdir', target, local_input],
                env={**os.environ, 'XDG_CACHE_HOME': str(root / 'cache'), 'XDG_CONFIG_HOME': str(root / 'config')})
            extension = format.split(':', 1)[0]
            converted = target / (path.stem + '.' + extension)
            if not converted.is_file():
                raise ValueError('LibreOffice 未产生输出，请检查格式或加密状态')
            save_new(output, lambda staging: shutil.copyfile(converted, staging))
    return result(plugin, output)


async def render_pdf(plugin, invocation, path, pages):
    if not pages or len(pages) > 4 or any(type(n) is not int or n < 1 for n in pages):
        raise ValueError('每次指定1到4个页码，从1开始')
    from pypdf import PdfReader
    count = await asyncio.to_thread(lambda: len(PdfReader(path).pages))
    if any(n > count for n in pages):
        raise ValueError('页码超出范围，共 ' + str(count) + ' 页')
    folder = plugin.workspace.path('output/previews/' + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    previews, files = [], []
    for number in dict.fromkeys(pages):
        prefix = folder / ('page-' + str(number))
        await command(['pdftoppm', '-f', number, '-l', number, '-singlefile', '-scale-to', 1400, '-png', path, prefix])
        image = prefix.with_suffix('.png')
        files.append(image)
        previews.append({'page': number, **result(plugin, image)})
    vision = plugin.preview_images(invocation, files[:2], note='本次渲染的文档页面预览；检查排版、文字、表格和裁切。其余页面可分批调用预览。')
    return {'total_pages': count, 'previews': previews, 'vision': vision}
