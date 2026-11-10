"""Authenticated ImageStore transport; cookies stay inside the plugin."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import unquote, urlsplit
import httpx


def base_url(value, optional=False):
    value=str(value or '').strip().rstrip('/')
    if not value and optional:return ''
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('请输入完整HTTP/HTTPS基础地址，不含账号、查询参数或片段')
    return value


def api_path(path):
    if not isinstance(path,str) or not path.startswith('/api/'):
        raise ValueError('path须为/api/开头的相对路径')
    decoded=unquote(path)
    if any(c in decoded for c in ('?','#','\\',':','\r','\n')) or any(p in ('.','..') for p in decoded.split('/')) or '//' in decoded:
        raise ValueError('path不能含域名、查询字符串、片段或目录跳转；查询参数使用query')
    return path


class GalleryClient:
    def __init__(self,config):
        self.config=config
        self.lock=asyncio.Lock()
        self.http=None
        self.signature=None
        self.authenticated=False

    async def close(self):
        async with self.lock:
            if self.http:await self.http.aclose()
            self.http=None
            self.signature=None
            self.authenticated=False

    async def session(self):
        signature=(base_url(self.config['base_url']),self.config.get('password',''),self.config['timeout'])
        if self.signature!=signature:
            if self.http:await self.http.aclose()
            self.http=httpx.AsyncClient(base_url=signature[0]+'/',timeout=int(signature[2]),trust_env=False,follow_redirects=False)
            self.signature=signature
            self.authenticated=False
        return self.http

    async def login(self,http):
        password=self.config.get('password','')
        if not password:raise ValueError('请先配置图库管理密码')
        response=await http.post('api/auth/login',json={'password':password})
        if response.status_code!=200:raise ValueError('图库登录失败（HTTP '+str(response.status_code)+'）')
        self.authenticated=True

    async def request(self,method,path,*,query=None,body=None,form=None,upload=None,admin=False,max_bytes=524288,allow_oversize=False,download_dir=None,download_response=False):
        method=method.upper()
        if method not in ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'):raise ValueError('HTTP方法无效')
        path=api_path(path)
        if upload and body is not None:raise ValueError('文件上传不能同时提供JSON body，请使用form')
        async with self.lock:
            try:
                http=await self.session()
                if admin and not self.authenticated:await self.login(http)
                for attempt in range(2):
                    kwargs={'params':query}
                    if upload:
                        upload[1].seek(0)
                        kwargs.update(data=form or {},files={'file':upload})
                    elif form is not None:kwargs['data']=form
                    elif body is not None:kwargs['json']=body
                    async with http.stream(method,path.lstrip('/'),**kwargs) as response:
                        if response.status_code==401 and admin and attempt==0:
                            self.authenticated=False
                        else:
                            mime=response.headers.get('content-type','').split(';')[0]
                            binary=not mime.startswith('text/') and mime!='application/json' and not mime.endswith('+json')
                            spool=download_dir is not None and 200<=response.status_code<300 and response.status_code not in (204,205) and method!='HEAD' and (download_response or binary)
                            limit=max_bytes if spool else min(max_bytes,524288)
                            temporary=None
                            output=None
                            handed_off=False
                            try:
                                if spool:
                                    Path(download_dir).mkdir(parents=True,exist_ok=True)
                                    fd,name=tempfile.mkstemp(prefix='gallery-',suffix='.part',dir=download_dir)
                                    temporary=Path(name)
                                    output=os.fdopen(fd,'wb')
                                content=bytearray()
                                size=0
                                async for part in response.aiter_bytes(chunk_size=65536):
                                    size+=len(part)
                                    if size>limit:
                                        if allow_oversize:return response.status_code,dict(response.headers),None
                                        raise ValueError('图库响应超过大小上限，请调整文件上限或分页查询')
                                    if output:output.write(part)
                                    else:content.extend(part)
                                if output:
                                    output.close()
                                    output=None
                                    handed_off=True
                                    return response.status_code,dict(response.headers),temporary
                                return response.status_code,dict(response.headers),bytes(content)
                            finally:
                                if output:output.close()
                                if temporary and not handed_off:temporary.unlink(missing_ok=True)
                    await self.login(http)
                raise ValueError('图库认证失败')
            except httpx.HTTPError:
                raise RuntimeError('图库连接失败或超时；写入结果可能未知，未自动重试') from None

    async def json(self,method,path,**kwargs):
        status,headers,content=await self.request(method,path,**kwargs)
        if not 200<=status<300:raise RuntimeError('图库HTTP '+str(status))
        try:return json.loads(content) if content else None
        except ValueError:raise RuntimeError('图库返回了无效JSON') from None
