"""Immutable plugin artifacts addressed by unguessable capability URLs."""
import json
import mimetypes
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def preview_images(plugin, invocation, paths, note):
    if invocation.origin != 'agent':
        return {'queued': False, 'reason': '当前不是 Agent 模型调用'}
    _, model = plugin.runtime.config.settings.selected_model(model_id=invocation.model_id or None)
    if not model or not model.capabilities.image:
        return {'queued': False, 'reason': '当前模型未启用图像能力，不能声称已目视检查'}
    import base64
    import io
    from PIL import Image
    content = [{'type': 'text', 'text': note}]
    relative = []
    for path in paths[:2]:
        path = Path(path)
        if path.is_absolute():
            path = path.resolve().relative_to(plugin.workspace.root.resolve())
        path = plugin.workspace.path(path.as_posix(), allow_root=False)
        relative.append(path.relative_to(plugin.workspace.root).as_posix())
        with Image.open(path) as image:
            image.thumbnail((1100, 1100))
            buffer = io.BytesIO()
            image.convert('RGB').save(buffer, format='JPEG', quality=85)
        content.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()}})
    if not relative:
        return {'queued': False, 'reason': '没有预览图片'}
    invocation.temporary_next.append({'role': 'user', 'content': content, '_observation': True, '_preview_paths': relative})
    return {'queued': True, 'count': len(relative), 'scope': 'next_model_request'}


def publish(plugin, path, name=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('附件不存在或超过20 MiB')
    token = uuid.uuid4().hex + uuid.uuid4().hex
    folder = plugin.runtime.config.root / 'artifacts' / token
    folder.mkdir(parents=True, mode=0o700)
    shutil.copyfile(path, folder / 'content')
    name = Path(name or path.name).name
    mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    metadata = {'name': name, 'mime': mime, 'plugin': plugin.id, 'created_at': time.time(), 'expires': time.time()+604800}
    (folder / 'metadata.json').write_text(json.dumps(metadata))
    return {'url': '/api/artifacts/' + token, 'name': name, 'mime': mime, 'expires': metadata['expires']}


def media_url(value):
    if value.startswith('/api/artifacts/'):
        return os.environ.get('SAKUBOT_INTERNAL_URL', 'http://sakubot:6190').rstrip('/') + value
    return value


def register_artifacts(app, runtime):
    @app.get('/api/artifacts/{token}')
    async def download(token: str):
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            raise HTTPException(404, '附件不存在')
        folder = runtime.config.root / 'artifacts' / token
        try:
            data = json.loads((folder / 'metadata.json').read_text())
            if data['expires'] < time.time():
                raise HTTPException(410, '附件已过期')
            return FileResponse(folder / 'content', media_type=data['mime'], filename=data['name'],
                content_disposition_type='inline' if data['mime'].startswith(('image/','video/','audio/')) else 'attachment')
        except (OSError, ValueError, KeyError):
            raise HTTPException(404, '附件不存在') from None


async def cleanup_loop(root):
    import asyncio
    while True:
        folder = root / 'artifacts'
        if folder.is_dir():
            for item in folder.iterdir():
                if not item.is_dir() or not re.fullmatch(r'[0-9a-f]{64}', item.name):
                    continue
                try:
                    metadata = json.loads((item / 'metadata.json').read_text())
                    if metadata['expires'] < time.time():
                        shutil.rmtree(item)
                except (OSError, ValueError, KeyError):
                    continue
        await asyncio.sleep(3600)
