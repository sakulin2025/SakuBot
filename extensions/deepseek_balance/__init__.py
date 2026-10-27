import json
from datetime import datetime, timezone
from urllib.parse import urlsplit
import httpx
from sakubot.plugin import Plugin
from sakubot.plugin_support import field, collection


class Extension(Plugin):
    name = 'deepseek_balance'

    def setup(self):
        self.function(self.balance, name='deepseek_balance')
        self.management('调用余额',[collection('providers','供应商',[field('id','ID'),field('name','名称'),field('last_balance','最近余额')],create=False,edit=False,remove=False,row_commands=[{'id':'query','label':'查询余额'}])],self.view,self.manage)

    def official(self, provider):
        try:
            url=urlsplit(provider.api_base)
            return url.scheme=='https' and url.hostname=='api.deepseek.com' and url.port in (None,443) and not url.username and not url.password
        except ValueError:return False

    def view(self):
        return {'data':{'providers':[{'id':p.id,'name':p.name,'last_balance':self.state.get('balance:'+p.id)} for p in self.runtime.config.settings.providers if self.official(p)]}}

    async def manage(self,data):return await self.balance(provider_id=data['key'])

    async def balance(self, invocation=None, provider_id:str=''):
        """主动查询 DeepSeek 官方供应商的余额。用户问“你还有多少钱”“多少大白饭”“饭钱”“伙食费”“余额/额度”且指 AI 的调用经费时使用；不要回答自己不吃饭，不猜余额。返回账户金额与实际币种，不换算为 token、顿数或聊天次数。仅主动查询，不轮询；复用框架供应商 Key，不返回密钥。

        Args:
            provider_id(string): 可选供应商 ID，留空使用当前 Agent 的模型供应商。
        """
        settings=self.runtime.config.settings
        provider=next((p for p in settings.providers if p.id==provider_id),None) if provider_id else settings.selected_model(model_id=(invocation.model_id or None) if invocation else None)[0]
        if provider is None or not self.official(provider):raise ValueError('请选择 DeepSeek 官方 HTTPS 供应商')
        if not provider.api_key:raise ValueError('供应商没有 API Key')
        try:
            async with httpx.AsyncClient(timeout=15,trust_env=False,follow_redirects=False) as client:
                response=await client.get('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+provider.api_key})
            if response.status_code!=200:raise ValueError('余额查询失败（HTTP '+str(response.status_code)+'）')
            data=response.json()
            if not isinstance(data.get('is_available'),bool) or not isinstance(data.get('balance_infos'),list):raise ValueError('余额接口格式无效')
            result={'provider_id':provider.id,'is_available':data['is_available'],'balance_infos':[{k:item.get(k) for k in ('currency','total_balance','granted_balance','topped_up_balance')} for item in data['balance_infos']], 'fetched_at':datetime.now(timezone.utc).isoformat()}
            self.state.set('balance:'+provider.id,result)
            return result
        except httpx.HTTPError:raise ValueError('余额查询网络失败或超时') from None
