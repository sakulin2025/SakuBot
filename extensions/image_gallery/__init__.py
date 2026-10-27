import asyncio
import time
import uuid
from pathlib import Path
import httpx
from sakubot.plugin import Plugin
from sakubot.plugin_support import field, collection, settings_section, fields_schema


class Extension(Plugin):
    name='image_gallery'

    def setup(self):
        self.config=self.configure({'base_url':'','timeout':20,'max_bytes':8})
        self.fields=[field('base_url','URL',required=True),field('timeout','超时 · 秒','number',min=1,max=120),field('max_bytes','图片上限 · MiB','number',min=1,max=20)]
        self.lock=asyncio.Lock()
        self.function(self.fetch,name='fetch_anime_image');self.function(self.pending,name='count_pending_images');self.function(self.send,name='gallery_send')
        self.management('图库',[collection('recent','最近取图',[field('id','图片 ID'),field('url','图片','image'),field('path','工作空间路径')],create=False,edit=False,remove=False,commands=[{'id':'fetch','label':'取图'},{'id':'pending','label':'待审数量'}]),settings_section(self.fields)],self.view,self.manage)

    def availability(self):
        ok=bool(self.config.get('base_url'))
        return {'available':ok,'reason':'' if ok else '尚未配置图库 URL'}

    def view(self):return {'data':{'config':self.config.public(),'recent':self.state.get('recent',[])}}

    async def manage(self,data):
        if data['section']=='config':self.config.patch(data['value'],fields_schema(self.fields));return {'saved':True}
        return await self.pending() if data['command']=='pending' else await self.fetch()

    async def get(self,path,allow_oversize=False):
        try:
            async with httpx.AsyncClient(timeout=int(self.config['timeout']),trust_env=False,follow_redirects=False) as client:
                async with client.stream('GET',self.config['base_url'].rstrip('/')+path) as response:
                    if response.status_code!=200:raise ValueError('图库 HTTP '+str(response.status_code))
                    content=bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content)>int(self.config['max_bytes'])*1024*1024:
                            if allow_oversize:return dict(response.headers),None
                            raise ValueError('图片超过大小上限')
                    return dict(response.headers),bytes(content)
        except httpx.HTTPError:raise ValueError('图库网络失败或超时') from None

    async def pending(self):
        """查询图库待审核图片数量；用户问还有多少没审核、待审积压时使用，只返回数量。"""
        import json
        _,content=await self.get('/api/stats')
        count=json.loads(content).get('counts',{}).get('pending')
        if type(count) is not int:raise ValueError('图库没有提供待审核数量')
        return {'pending':count}

    async def fetch(self, orientation:str=''):
        """随机获取审核通过的图片，返回图片 ID、共享工作空间路径和框架附件 URL。horizontal 横图、vertical 竖图，留空随机。主 Agent 可用 gallery_send 发送，协作 Agent 把结果交给主 Agent；不可把本地路径当远端 URL。图片 ID 可用于记忆和引用。"""
        import json
        orientation={'横':'horizontal','竖':'vertical'}.get(orientation,orientation)
        if orientation not in ('','horizontal','vertical'):raise ValueError('方向为 horizontal、vertical 或空')
        async with self.lock:
            recent=self.state.get('recent',[])
            for _ in range(4):
                headers,content=await self.get('/api/images/random'+('?aspect_ratio='+orientation if orientation else ''),allow_oversize=True)
                identifier=headers.get('x-image-id','')
                if not identifier or any(row['id']==identifier for row in recent[-20:]):continue
                from urllib.parse import quote
                _,metadata=await self.get('/api/images/'+quote(identifier,safe='')+'/meta')
                if json.loads(metadata).get('review_status')!='approved':continue
                if content is None:headers,content=await self.get('/api/images/'+quote(identifier,safe='')+'/preview')
                mime=headers.get('content-type','').split(';')[0]
                extension={'image/jpeg':'.jpg','image/png':'.png','image/gif':'.gif','image/webp':'.webp','image/bmp':'.bmp'}.get(mime)
                if extension is None:raise ValueError('图库返回了非图片内容')
                folder=self.workspace.path('artifacts/gallery');folder.mkdir(parents=True,exist_ok=True)
                path=folder/(uuid.uuid4().hex+extension);path.write_bytes(content)
                artifact=self.artifact(path)
                result={'id':identifier,**artifact,'path':path.relative_to(self.workspace.root).as_posix(),'at':time.time()}
                self.state.set('recent',(recent+[result])[-50:])
                return result
            raise ValueError('图库未提供符合条件的新图片')

    async def send(self,invocation,path:str):
        """发送共享工作空间内已取得的图库图片，仅主 Agent 使用。path 是 fetch_anime_image 返回的相对路径。"""
        target=self.workspace.path(path,allow_root=False)
        artifact=self.artifact(target)
        await self.respond_main([{'type':'image',**artifact}],invocation=invocation)
        return {'sent':True,**artifact}
