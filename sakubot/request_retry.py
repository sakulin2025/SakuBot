"""Classification and bounded backoff for a single model HTTP request."""
import asyncio
import random

QUOTA=('insufficient_quota','quota_exceeded','billing_hard_limit','billing_not_active',
       'insufficient balance','insufficient_balance','credit balance','credits exhausted','insufficient funds','insufficient_funds','quota exhausted','quota exceeded',
       'balance is not enough','payment required','余额不足','额度不足','额度用尽','欠费')
NETWORK={'ConnectError','ConnectTimeout','ReadTimeout','WriteTimeout','PoolTimeout','ReadError',
         'WriteError','RemoteProtocolError','ProxyError','CloseError','IncompleteResponse'}


def classify(exc):
    details=getattr(exc,'details',{})
    diagnostic=str(details.get('response_body',''))+' '+str(details.get('error',''))
    lowered=diagnostic.lower()
    if details.get('status')==402 or any(word in lowered for word in QUOTA):return False,'quota'
    status=details.get('status')
    if status in (401,403):return False,'authentication'
    if status in (408,425,429) or (isinstance(status,int) and 500<=status<=599):return True,'transient_http'
    if any(code in lowered for code in ('rate_limit_exceeded','server_overloaded','overloaded_error','internal_server_error')):return True,'transient_service'
    if details.get('error_type') in NETWORK:return True,'network'
    return False,'request'


def delay(exc,attempt):
    header=getattr(exc,'details',{}).get('headers',{}).get('retry-after')
    try:return min(60,max(0,float(header))) if header is not None else min(30,2**attempt)+random.uniform(0,.5)
    except (ValueError,TypeError):return min(30,2**attempt)


async def complete(operation,settings,on_retry=None,on_failure=None,on_attempt=None):
    policy=settings.request_retry
    for attempt in range(policy.max_retries+1):
        if on_attempt:await on_attempt(attempt)
        try:return await operation()
        except asyncio.CancelledError:raise
        except Exception as exc:
            retryable,reason=classify(exc)
            retry=retryable and attempt<policy.max_retries
            if retry:
                wait=delay(exc,attempt+1)
                if on_retry:await on_retry(exc,attempt+1,wait,reason)
                await asyncio.sleep(wait)
            else:
                if on_failure:await on_failure(exc,retryable,attempt,reason)
                raise
