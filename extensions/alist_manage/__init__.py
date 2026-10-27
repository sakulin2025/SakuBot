import asyncio
import json
from pathlib import Path
from sakubot.plugin import Plugin
from sakubot.plugin_support import field, collection, settings_section, fields_schema
import time
from .client import AList, PluginError


class Extension(Plugin):
    name = 'alist_manage'

    def setup(self):
        self.config=self.configure({'base_url':'','token':'','username':'','password':'','path_password':'','public_url':'','timeout':30,'max_upload_mb':20,'folder_rules':[]},secrets=('token','password','path_password'))
        self.client=AList(self.config);self.lock=asyncio.Lock();self.previews={}
        self.fields=[field('base_url','URL',required=True),field('token','Token','secret'),field('username','用户名'),field('password','密码','secret'),field('path_password','目录密码','secret'),field('public_url','公开 URL'),field('timeout','超时 · 秒','number',min=1,max=300),field('max_upload_mb','上传上限 · MiB','number',min=1,max=100)]
        self.function(self.scan,name='alist_scan_folders');self.function(self.browse,name='alist_browse');self.function(self.write,name='alist_write')
        self.management('AList',[collection('folders','目录',[field('path','第一层目录',readonly=True),field('ignore','忽略','boolean'),field('download','下载','boolean'),field('add','添加','boolean'),field('delete','删除','boolean')],key='path',create=False,remove=False,commands=[{'id':'scan','label':'扫描目录'}]),settings_section(self.fields)],self.view,self.manage)
    def availability(self):
        return {'available':bool(self.config.get('base_url')),'reason':'' if self.config.get('base_url') else '尚未配置 AList'}
    def view(self):return {'data':{'config':self.config.public([f['key'] for f in self.fields]),'folders':self.config['folder_rules']}}
    async def manage(self,data):
        if data['section']=='config':self.config.patch(data['value'],fields_schema(self.fields));return {'saved':True}
        if data['action']=='command':return await self.scan()
        async with self.lock:
            item=next((r for r in self.config['folder_rules'] if r['path']==data['key']),None)
            if item is None:raise ValueError('目录已不存在')
            if set(data['value'])-{'ignore','download','add','delete'} or any(type(v) is not bool for v in data['value'].values()):raise ValueError('目录开关无效')
            item.update(data['value']);self.config.save();return {'saved':True}

    async def scan(self):
        """用户扫描 AList 第一层文件夹并填入插件配置页，保留已有权限，新目录默认忽略。"""
        try:
            async with self.lock:
                rules = await asyncio.to_thread(self.client.discover)
                self.config['folder_rules'] = rules
                self.config.save()
            return f'已同步 {len(rules)} 个第一层目录。请到 AList 文件管理插件的配置页面调整忽略、下载、添加、删除开关。'
        except PluginError as exc:
            return str(exc)

    async def browse(self, path: str='/', action: str='list', page: int=1):
        """浏览 AList 文件。仅 list/info 返回元数据；download 才返回下载链接，需所在第一层目录开放下载权限。禁止绕过插件调用旧脚本。

                Args:
                    path(string): AList 绝对路径，默认根目录。
                    action(string): list 列目录、info 详情、download 获取文件下载链接。
                    page(int): 列表页码，每页最多200项。
                """
        try:
            if action == 'list':
                data = await asyncio.to_thread(self.client.listing, path, page)
            elif action in ('info', 'download'):
                data = await asyncio.to_thread(self.client.info, path, action == 'download')
            else:
                raise PluginError('action 只能是 list/info/download')
            return data
        except PluginError as exc:
            return str(exc)

    async def write(self, invocation, action: str, path: str, target: str='', source_url: str='', confirmed: bool=False):
        """管理 AList 文件。先 confirmed=false 预览路径和后果，得到用户明确同意后才能 confirmed=true 执行同一操作。添加禁止覆盖；移动/重命名须有删除及添加权限，复制须有来源下载及目标添加权限。

                Args:
                    action(string): mkdir/upload/remove/rename/move/copy。
                    path(string): 完整源路径；mkdir/upload 时为完整目标路径。
                    target(string): rename 为新文件名；move/copy 为已存在的目标目录。
                    source_url(string): upload 的 http/https 文件来源，下载后上传到 path。
                    confirmed(bool): 用户已明确确认本次预览才为 true，默认 false。
                """
        key = (invocation.agent_id, action, path, target, source_url)
        try:
            async with self.lock:
                self.client.check_write(action, path, target)
                now = time.monotonic()
                self.previews = {k: t for k, t in self.previews.items() if now - t < 600}
                if not confirmed:
                    self.previews[key] = now
                    return {'preview': True, 'action': action, 'path': path, 'target': target, 'consequence': '永久删除目标及其内容' if action == 'remove' else '将修改文件或目录', 'next': '向用户复述并取得明确确认后，使用完全相同的参数执行'}
                if key not in self.previews:
                    raise PluginError('缺少有效预览，请先预览并让用户确认；预览10分钟有效')
                self.previews.pop(key)
                data = await asyncio.to_thread(self.client.write, action, path, target, source_url)
            return data
        except PluginError as exc:
            return str(exc)

    def settings_saved(self):
        self.client.token = ''
