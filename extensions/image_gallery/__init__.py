"""ImageStore tools, authenticated API access and metadata-only push events."""
import asyncio
import json
import mimetypes
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sakubot.plugin import Plugin
from sakubot.plugin_support import field, collection
from .client import GalleryClient, base_url
from .polling import GalleryPolling


class Extension(GalleryPolling,Plugin):
    name='image_gallery'

    def setup(self):
        metadata=json.loads((Path(__file__).parent/'plugin.json').read_text())
        self.fields=metadata['settings']['fields']
        defaults={row['key']:row.get('default','') for row in self.fields}
        saved_path=self.data_dir/'config.json'
        saved=json.loads(saved_path.read_text()) if saved_path.is_file() else {}
        if 'max_bytes' in saved and 'download_limit_mib' not in saved:
            defaults['download_limit_mib']=saved['max_bytes']
        self.config=self.configure(defaults,secrets=('password',))
        if 'max_bytes' in self.config:
            self.config.pop('max_bytes')
            self.config.save()
        self.client=GalleryClient(self.config)
        self.lock=asyncio.Lock()
        self.function(self.fetch,name='fetch_anime_image')
        self.function(self.pending,name='count_pending_images')
        self.function(self.send,name='gallery_send')
        self.function(self.image_link,name='gallery_image_link')
        self.register_admin()
        self.setup_polling()
        self.management('图库',[
            collection('recent','最近取图',[field('id','图片 ID'),field('url','图片','image'),field('path','工作空间路径')],
                create=False,edit=False,remove=False,commands=[{'id':'fetch','label':'取图'},{'id':'pending','label':'待审数量'}]),
            collection('polling','轮询',[field('phase','状态'),field('next_at','下次检查'),field('last_at','上次检查'),field('error','错误')],create=False,edit=False,remove=False),
            collection('batches','推送批次',[field('batch_id','批次'),field('target','目标'),field('image_ids','图片 ID'),field('replay','重发','boolean'),field('status','状态'),field('fetched_at','时间')],key='batch_id',create=False,edit=False,remove=False)
        ],self.view,self.manage,group_id='media')
        self.settings_form(self.fields,validate=self.validate_settings,on_saved=self.settings_saved)

    def register_admin(self):
        exists=self.runtime.registry.tools.get('gallery_api')
        if self.config.get('password'):
            if not exists:self.function(self.api_call,name='gallery_api')
        elif exists and exists.plugin_id==self.id:
            del self.runtime.registry.tools['gallery_api']

    def availability(self):
        ok=bool(self.config.get('base_url'))
        return {'available':ok,'reason':'' if ok else '尚未配置图库 URL'}

    def prompt_context(self,invocation):
        return '图库图片按实际ID引用。收藏管理对应合集Collection，调用前读图库技能和API文档；需要管理权限时用gallery_api。推送事件只有图片ID，按需取图，不默认向任何人发送。外链只用gallery_image_link生成，不能传播内部地址或认证信息。'

    def view(self):
        poll=self.state.get('poll_status',{})
        rows=[]
        for batch in self.state.get('batches',[]):
            rows.append({**{k:v for k,v in batch.items() if k not in ('base_url','acknowledged')},
                'image_ids':', '.join(batch['image_ids']),'status':'已登记' if batch.get('completed_at') else '待处理'})
        return {'data':{'recent':self.state.get('recent',[]),'batches':rows,
            'polling':[{**poll,**{k:datetime.fromtimestamp(poll[k],ZoneInfo(self.config['timezone'])).isoformat() if poll.get(k) else '' for k in ('next_at','last_at')}}]}}

    async def manage(self,data):
        return await self.pending() if data.get('command')=='pending' else await self.fetch()

    async def validate_settings(self,values):
        base_url(values['base_url'])
        base_url(values['external_url'],optional=True)
        if values['interval_min_minutes']>values['interval_max_minutes']:raise ValueError('最短间隔不能大于最长间隔')
        if values['count_min']>values['count_max']:raise ValueError('最少张数不能大于最多张数')
        for key in ('count_min','count_max','timeout','download_limit_mib','transfer_limit_mib','delay_minutes'):
            if type(values[key]) is not int:raise ValueError('张数、超时、大小及延迟须为整数')
        try:
            ZoneInfo(values['timezone'])
            for key in ('quiet_start','quiet_end'):
                if datetime.strptime(values[key],'%H:%M').strftime('%H:%M')!=values[key]:raise ValueError()
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('请填写有效时区及HH:MM时间') from None
        if values['quiet_enabled'] and values['quiet_start']==values['quiet_end']:raise ValueError('免打扰开始与结束时间不能相同')
        if values['poll_enabled'] and not values.get('password'):raise ValueError('启用推送获取前请配置管理密码')
        if not values['push_target'].strip():raise ValueError('推送目标标识不能为空')
        # Read-only credential validation happens only when the user saves configuration.
        if values.get('password'):
            client=GalleryClient(values)
            try:
                status,_,_=await client.request('GET','/api/auth/check',admin=True)
                if status not in (200,204):raise ValueError('图库登录状态验证失败，配置未保存')
            finally:await client.close()

    async def settings_saved(self):
        await self.client.close()
        self.register_admin()
        self.poll_changed.set()

    async def stop(self):
        await super().stop()
        await self.client.close()

    def download_directory(self):
        return self.workspace.path('tmp/gallery-downloads')

    async def get(self,path,allow_oversize=False,query=None):
        status,headers,content=await self.client.request('GET',path,query=query,
            max_bytes=self.config['download_limit_mib']*1024*1024,allow_oversize=allow_oversize,
            download_dir=self.download_directory())
        if status!=200:
            if isinstance(content,Path):content.unlink(missing_ok=True)
            raise ValueError('图库HTTP '+str(status))
        return headers,content

    async def pending(self):
        """查询图库待审核图片数量，只返回pending整数，不修改审核或推送记录。"""
        result=await self.client.json('GET','/api/stats')
        count=result.get('counts',{}).get('pending')
        if type(count) is not int:raise ValueError('图库没有提供待审核数量')
        return {'pending':count}

    def save_file(self,temporary,mime,relative=''):
        if not isinstance(temporary,Path):raise ValueError('图库没有返回可下载的图片或文件')
        target=None
        created=False
        try:
            if relative:
                target=self.workspace.path(relative,allow_root=False)
                if target.exists():raise ValueError('下载目标已存在，请选择其他路径')
            else:
                ext=mimetypes.guess_extension(mime) or '.bin'
                target=self.workspace.path('artifacts/gallery/'+uuid.uuid4().hex+ext)
            target.parent.mkdir(parents=True,exist_ok=True)
            try:
                os.link(temporary,target)
                created=True
            except OSError as exc:
                # Different mounts may not support hard links; still copy in bounded chunks.
                import errno
                if exc.errno not in (errno.EXDEV,errno.EPERM,errno.ENOTSUP):raise
                with target.open('xb') as output:
                    created=True
                    with temporary.open('rb') as source:shutil.copyfileobj(source,output,65536)
            limit=max(self.config['download_limit_mib'],self.config['transfer_limit_mib'])*1024*1024
            return {**self.artifact(target,max_bytes=limit),'path':target.relative_to(self.workspace.root).as_posix()}
        except BaseException:
            if created and target:target.unlink(missing_ok=True)
            raise
        finally:temporary.unlink(missing_ok=True)

    async def fetch(self,orientation:str='',image_id:str=''):
        """随机获取审核通过图片，或按实际image_id取图，返回id、工作空间path、框架附件url。orientation为horizontal/vertical或空，仅随机模式使用。过大的原图会尝试预览。主智能体用gallery_send发送；不得将本地路径当成外部链接，外部推广用gallery_image_link。指定ID取图不等于已确认适合公开分享。"""
        orientation={'横':'horizontal','竖':'vertical'}.get(orientation,orientation)
        if orientation not in ('','horizontal','vertical'):raise ValueError('orientation为horizontal/vertical或空')
        async with self.lock:
            recent=self.state.get('recent',[])
            for _ in range(1 if image_id else 4):
                path='/api/images/'+quote(image_id,safe='') if image_id else '/api/images/random'
                headers,content=await self.get(path,allow_oversize=True,
                    query={'aspect_ratio':orientation} if not image_id and orientation else None)
                identifier=headers.get('x-image-id','') or image_id
                if not identifier or (not image_id and any(row['id']==identifier for row in recent[-20:])):
                    if isinstance(content,Path):content.unlink(missing_ok=True)
                    continue
                if content is None:headers,content=await self.get('/api/images/'+quote(identifier,safe='')+'/preview')
                mime=headers.get('content-type','').split(';')[0]
                if mime not in ('image/jpeg','image/png','image/gif','image/webp','image/bmp'):
                    if isinstance(content,Path):content.unlink(missing_ok=True)
                    raise ValueError('图库返回非图片内容')
                result={'id':identifier,**(await asyncio.to_thread(self.save_file,content,mime)),'at':time.time()}
                self.state.set('recent',(recent+[result])[-50:])
                return result
            raise ValueError('图库未提供符合条件的新图片')

    async def image_link(self,image_id:str):
        """按实际图片ID生成公开原图链接，仅用于适合公开分享的图片。必须配置external_url；不使用内部地址、不含密码Cookie、不生成合集或管理链接。链接不失效，知道地址即可访问。"""
        if not isinstance(image_id,str) or not image_id.strip():raise ValueError('请输入实际图片ID')
        public=base_url(self.config.get('external_url',''),optional=True)
        if not public:raise ValueError('尚未配置外部访问URL')
        return {'id':image_id,'url':public+'/api/images/'+quote(image_id,safe='')}

    async def api_call(self,method:str='GET',path:str='/api/stats',query:dict=None,body:dict|list|None=None,form:dict=None,upload_path:str='',download_path:str=''):
        """调用图库完整API，包括合集收藏、图片元数据、审核、上传、删除、推送队列及管理接口。必须配置管理密码，插件自动管理登录Cookie。操作前重新读取图库技能与API参考文档，不能猜字段；写操作按用户要求执行，结果未知不能盲目重试。返回ok/status/content_type/data，二进制保存为file对象；非2xx保留HTTP结果，不代表成功。

        Args:
            method(string): GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS。
            path(string): /api/开头相对路径，不含域名或查询字符串。
            query(object): URL查询参数，数组按逗号连接，布尔转true/false。
            body(object): JSON对象或数组；不要与form/upload_path同时使用。
            form(object): 表单字段，图片上传需要source、image_id等，不是JSON请求体。
            upload_path(string): 可选工作空间文件路径，作为multipart的file字段上传。
            download_path(string): 可选工作空间保存路径，不覆盖已有文件；未指定时二进制保存到artifacts/gallery。
        """
        if not self.config.get('password'):raise ValueError('请先配置图库管理密码')
        if body is not None and form is not None:raise ValueError('body与form不能同时使用')
        params={k:','.join(map(str,v)) if isinstance(v,list) else str(v).lower() if isinstance(v,bool) else v for k,v in (query or {}).items() if v is not None}
        handle=None
        try:
            upload=None
            if upload_path:
                local=self.workspace.path(upload_path,allow_root=False)
                if not local.is_file() or local.stat().st_size>self.config['transfer_limit_mib']*1024*1024:
                    raise ValueError('上传文件不存在或超过API文件传输上限')
                handle=local.open('rb')
                upload=(local.name,handle,mimetypes.guess_type(local.name)[0] or 'application/octet-stream')
            status,headers,content=await self.client.request(method,path,query=params,body=body,form=form,upload=upload,admin=True,max_bytes=self.config['transfer_limit_mib']*1024*1024,
                download_dir=self.download_directory(),download_response=bool(download_path))
        finally:
            if handle:handle.close()
        mime=headers.get('content-type','').split(';')[0]
        result={'ok':200<=status<300,'status':status,'content_type':mime,'data':None}
        if headers.get('x-image-id'):result['image_id']=headers['x-image-id']
        if isinstance(content,Path):
            result['file']=await asyncio.to_thread(self.save_file,content,mime,download_path)
        elif mime=='application/json' or mime.endswith('+json'):
            try:result['data']=json.loads(content) if content else None
            except ValueError:raise RuntimeError('图库返回无效JSON') from None
        else:result['data']=content.decode(errors='replace')[:30000] if content else None
        return result

    async def send(self,invocation,path:str):
        """向当前主对话发送工作空间中的图库图片，path为fetch_anime_image或gallery_api返回的相对路径。"""
        artifact=await asyncio.to_thread(self.artifact,self.workspace.path(path,allow_root=False),
            max_bytes=max(self.config['download_limit_mib'],self.config['transfer_limit_mib'])*1024*1024)
        await self.respond_main([{'type':'image',**artifact}],invocation=invocation)
        return {'sent':True,**artifact}
