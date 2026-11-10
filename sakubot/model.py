import asyncio
import json
import math
import socket
import ssl
import time
from urllib.parse import urlsplit

import httpx


class TransportTrace:
    """Collects httpcore transport timings for a single model request."""

    def __init__(self):
        self.started = time.monotonic()
        self.connect = {}
        self.tls = {}
        self.send_headers = {}
        self.response_headers = {}
        self.body = {}
        self.first_reasoning_ms = None
        self.first_content_ms = None
        self.first_tool_ms = None

    def elapsed(self, at=None):
        return round(((time.monotonic() if at is None else at) - self.started) * 1000, 1)

    async def __call__(self, event, info):
        now = time.monotonic()
        if event == 'connection.connect_tcp.started':
            self.connect.setdefault('start', now)
        elif event == 'connection.connect_tcp.complete':
            start = self.connect.pop('start', None)
            if start is not None:
                self.connect['ms'] = round((now - start) * 1000, 1)
        elif event == 'connection.start_tls.started':
            self.tls.setdefault('start', now)
        elif event == 'connection.start_tls.complete':
            start = self.tls.pop('start', None)
            if start is not None:
                self.tls['ms'] = round((now - start) * 1000, 1)
        elif event == 'http11.send_request_headers.started':
            self.send_headers['start'] = now
        elif event == 'http11.send_request_headers.complete':
            start = self.send_headers.pop('start', None)
            if start is not None:
                self.send_headers['ms'] = round((now - start) * 1000, 1)
        elif event == 'http11.receive_response_headers.started':
            self.response_headers['start'] = now
        elif event == 'http11.receive_response_headers.complete':
            start = self.response_headers.pop('start', None)
            if start is not None:
                self.response_headers['ms'] = round((now - start) * 1000, 1)
            self.response_headers['at'] = now
        elif event == 'http11.receive_response_body.started':
            self.body.setdefault('first', now)
        elif event == 'http11.receive_response_body.complete':
            self.body['at'] = now
        elif event == 'http11.response_closed':
            self.body['closed'] = now

    def mark(self, name):
        if getattr(self, name + '_ms') is None:
            setattr(self, name + '_ms', self.elapsed())

    def summary(self):
        return {
            'new_connection': bool(self.connect),
            'tcp_ms': self.connect.get('ms'),
            'tls_ms': self.tls.get('ms'),
            'send_request_ms': self.send_headers.get('ms'),
            'server_headers_ms': self.response_headers.get('ms'),
            'first_body_ms': None if 'first' not in self.body else self.elapsed(self.body['first']),
            'first_reasoning_ms': self.first_reasoning_ms,
            'first_content_ms': self.first_content_ms,
            'first_tool_ms': self.first_tool_ms,
            'total_ms': self.elapsed(),
        }


class ModelRequestError(RuntimeError):
    def __init__(self, details):
        self.details = details
        super().__init__('模型请求失败：' + json.dumps(details, ensure_ascii=False))


def request_error(provider, model, response=None, error=None):
    # Only allow diagnostic headers; never persist authentication headers.
    details = {'provider_id': provider.id, 'model': model.model_id,
        'endpoint': provider.api_base.split('?')[0] + '/chat/completions'}
    if response is not None:
        body = response.text[:16000]
        if provider.api_key:
            body = body.replace(provider.api_key, '[redacted]')
        details.update(status=response.status_code, response_body=body,
            body_truncated=len(response.text) > 16000,
            headers={k: v for k, v in response.headers.items() if k.lower() in
                ('x-request-id', 'request-id', 'cf-ray', 'retry-after', 'content-type', 'date')})
    if error is not None:
        details.update(error_type=type(error).__name__, error=str(error)[:2000])
    return ModelRequestError(details)


class Model:
    def __init__(self, settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15), trust_env=False)

    async def close(self):
        await self.client.aclose()

    async def probe_network(self, provider, timeout=5):
        parts = urlsplit(provider.api_base)
        host = parts.hostname
        if not host:
            raise ValueError('模型接口地址缺少主机名')
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        started = time.monotonic()
        result = {'host': host, 'port': port, 'scheme': parts.scheme}
        try:
            resolved = await asyncio.to_thread(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
        except OSError as exc:
            result.update(error='dns:' + type(exc).__name__ + ':' + str(exc)[:200],
                          total_ms=round((time.monotonic() - started) * 1000, 1))
            return result
        result['dns_ms'] = round((time.monotonic() - started) * 1000, 1)
        addresses = []
        for item in resolved:
            address = item[4][0]
            if address not in addresses:
                addresses.append(address)
        result['addresses'] = addresses[:4]

        def connect(address):
            tcp_started = time.monotonic()
            sock = socket.create_connection((address, port), timeout=timeout)
            tcp_ms = round((time.monotonic() - tcp_started) * 1000, 1)
            try:
                if parts.scheme != 'https':
                    return tcp_ms, None, None
                tls_started = time.monotonic()
                try:
                    sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
                except OSError as exc:
                    return tcp_ms, None, 'tls:' + type(exc).__name__ + ':' + str(exc)[:200]
                return tcp_ms, round((time.monotonic() - tls_started) * 1000, 1), None
            finally:
                sock.close()

        failures = []
        for address in result['addresses']:
            try:
                tcp_ms, tls_ms, error = await asyncio.to_thread(connect, address)
            except OSError as exc:
                failures.append(address + ':' + type(exc).__name__)
                continue
            result.update(address=address, tcp_ms=tcp_ms, tls_ms=tls_ms,
                          total_ms=round((time.monotonic() - started) * 1000, 1))
            if error:
                result['error'] = error
            return result
        result.update(error='connect:' + ';'.join(failures),
                      total_ms=round((time.monotonic() - started) * 1000, 1))
        return result

    async def embed(self, provider, model, texts):
        payload = {'model': model.model_id, 'input': texts}
        if 'dimensions' in model.extra_body:
            payload['dimensions'] = model.extra_body['dimensions']
        try:
            response = await self.client.post(provider.api_base + '/embeddings', headers={'Authorization': 'Bearer ' + provider.api_key} if provider.api_key else {}, json=payload, timeout=45)
            if response.status_code != 200:
                raise RuntimeError('向量模型检查失败（HTTP ' + str(response.status_code) + '）')
            data = response.json()['data']
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError()
            ordered = sorted(data, key=lambda item: item['index'])
            if [item['index'] for item in ordered] != list(range(len(texts))):
                raise ValueError()
            vectors = []
            for item in ordered:
                vector = item['embedding']
                if not isinstance(vector, list) or not 1 <= len(vector) <= 65536 or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
                    raise ValueError()
                norm = math.sqrt(sum(v * v for v in vector))
                if not norm or not math.isfinite(norm):
                    raise ValueError()
                vectors.append([v / norm for v in vector])
            if len({len(vector) for vector in vectors}) != 1:
                raise ValueError()
            return vectors
        except httpx.HTTPError:
            raise RuntimeError('向量模型连接失败') from None
        except (KeyError, TypeError, ValueError, OverflowError):
            raise RuntimeError('向量模型返回格式无效') from None

    async def complete(self, messages, tools=None, lightweight=False, model_id=None, output_tokens=None, on_delta=None, on_request=None, settings=None, on_retry=None, on_failure=None, on_attempt=None, on_timing=None):
        from .request_retry import complete
        settings=settings or self.settings
        async def operation():
            return await self._complete_once(messages,tools,lightweight,model_id,output_tokens,on_delta,on_request,settings,on_timing)
        return await complete(operation,settings,on_retry,on_failure,on_attempt)

    async def _complete_once(self, messages, tools=None, lightweight=False, model_id=None, output_tokens=None, on_delta=None, on_request=None, settings=None, on_timing=None):
        provider, model = (settings or self.settings).selected_model(lightweight, model_id=model_id)
        if provider is None:
            raise RuntimeError("未选择已启用的文本模型")
        if not model.capabilities.tools:
            tools = None
        payload = dict(model.extra_body)
        if "max_tokens" not in payload and "max_completion_tokens" not in payload:
            payload["max_tokens"] = 4096
        if output_tokens is not None:
            payload.pop("max_completion_tokens", None)
            payload["max_tokens"] = output_tokens
        reserve = payload.get("max_tokens", payload.get("max_completion_tokens", 4096))
        prepared = self.prepare_messages(messages, tools, model, reserve)
        payload.update(model=model.model_id, messages=prepared, stream=on_delta is not None)
        if tools:
            payload["tools"] = tools
        else:
            payload.pop("tool_choice", None)
            payload.pop("parallel_tool_calls", None)
        if on_request is not None:
            on_request(payload)
        if on_delta is not None:
            return await self.stream(provider, model, payload, on_delta, on_timing)
        trace = TransportTrace() if on_timing is not None else None
        try:
            response = await self.client.post(provider.api_base + "/chat/completions",
                headers={"Authorization": "Bearer " + provider.api_key} if provider.api_key else {}, json=payload,
                extensions={'trace': trace} if trace is not None else None)
        except httpx.HTTPError as exc:
            raise request_error(provider, model, error=exc) from None
        finally:
            if on_timing is not None:
                on_timing(trace.summary())
        if response.status_code != 200:
            raise request_error(provider, model, response=response)
        try:
            body = response.json()
            message = body["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError()
            # Preserve reasoning_content for providers which require it on tool turns.
            allowed = ("role", "content", "tool_calls", "reasoning_content")
            result = {key: value for key, value in message.items() if key in allowed}
            result["role"] = "assistant"
            result["_finish_reason"] = body["choices"][0].get("finish_reason")
            if result.get("tool_calls") and not model.capabilities.tools:
                raise RuntimeError("模型返回了未启用的工具调用")
            if not isinstance(result.get("content"), (str, type(None))):
                result["content"] = json.dumps(result["content"], ensure_ascii=False)
            return result, body.get("usage", {})
        except (KeyError, IndexError, ValueError, TypeError):
            raise RuntimeError("模型接口返回格式不兼容 Chat Completions") from None

    async def stream(self, provider, model, payload, on_delta, on_timing=None):
        headers = {"Authorization": "Bearer " + provider.api_key} if provider.api_key else {}
        result = {'role': 'assistant', 'content': ''}
        calls, usage, completed = {}, {}, False
        trace = TransportTrace() if on_timing is not None else None

        async def packet(raw):
            nonlocal usage, completed
            if raw.strip() == '[DONE]':
                completed = True
                return
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError()
            if body.get('error'):
                raise request_error(provider, model, error=RuntimeError(json.dumps(body['error'], ensure_ascii=False).replace(provider.api_key, '[redacted]') if provider.api_key else json.dumps(body['error'], ensure_ascii=False)))
            if body.get('usage'):
                usage = body['usage']
            for choice in body.get('choices', []):
                if choice.get('index', 0) != 0:
                    continue
                if choice.get('finish_reason') is not None:
                    completed = True
                delta = choice.get('delta', {})
                content = delta.get('content')
                if isinstance(content, list):
                    content = ''.join(part.get('text', '') for part in content if isinstance(part, dict) and isinstance(part.get('text'), str))
                if isinstance(content, str) and content:
                    result['content'] += content
                    if trace is not None:
                        trace.mark('first_content')
                    await on_delta(content)
                reasoning = delta.get('reasoning_content')
                if isinstance(reasoning, str) and reasoning:
                    result['reasoning_content'] = result.get('reasoning_content', '') + reasoning
                    if trace is not None:
                        trace.mark('first_reasoning')
                for call in delta.get('tool_calls') or []:
                    if trace is not None:
                        trace.mark('first_tool')
                    index = call.get('index', 0)
                    current = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                    if call.get('id'):
                        current['id'] = call['id']
                    function = call.get('function') or {}
                    current['function']['name'] += function.get('name') or ''
                    current['function']['arguments'] += function.get('arguments') or ''

        try:
            async with self.client.stream('POST', provider.api_base + '/chat/completions', headers=headers, json=payload,
                    extensions={'trace': trace} if trace is not None else None) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise request_error(provider, model, response=response)
                if 'application/json' in response.headers.get('content-type', ''):
                    body = json.loads(await response.aread())
                    message = body['choices'][0]['message']
                    if not isinstance(message, dict):
                        raise ValueError()
                    result = {key: value for key, value in message.items() if key in ('role', 'content', 'tool_calls', 'reasoning_content')}
                    result['role'] = 'assistant'
                    if not isinstance(result.get('content'), (str, type(None))):
                        result['content'] = json.dumps(result['content'], ensure_ascii=False)
                    if isinstance(result.get('content'), str) and result['content']:
                        if trace is not None:
                            trace.mark('first_content')
                        await on_delta(result['content'])
                    if result.get('tool_calls') and not model.capabilities.tools:
                        raise RuntimeError('模型返回了未启用的工具调用')
                    return result, body.get('usage', {})
                data = []
                async for line in response.aiter_lines():
                    if not line:
                        if data:
                            await packet('\n'.join(data))
                            data = []
                    elif line.startswith('data:'):
                        data.append(line[5:].lstrip())
                if data:
                    await packet('\n'.join(data))
            if not completed:
                raise ModelRequestError({'provider_id':provider.id,'model':model.model_id,'error_type':'IncompleteResponse','error':'模型流式响应中断'})
            if calls:
                if not model.capabilities.tools:
                    raise RuntimeError('模型返回了未启用的工具调用')
                result['tool_calls'] = [calls[index] for index in sorted(calls)]
            return result, usage
        except httpx.HTTPError as exc:
            raise request_error(provider, model, error=exc) from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError('模型流式响应格式不兼容 Chat Completions') from None
        finally:
            if trace is not None:
                on_timing(trace.summary())

    def prepare_messages(self, messages, tools, model, reserve):
        prepared = []
        for message in messages:
            item = {key: value for key, value in message.items() if not key.startswith("_")}
            if isinstance(item.get("content"), list):
                content = []
                for part in item["content"]:
                    if part.get("type") == "image_url" and not model.capabilities.image:
                        content.append({"type": "text", "text": "[图像能力未启用]"})
                    elif part.get("type") == "input_audio" and not model.capabilities.audio:
                        content.append({"type": "text", "text": "[音频能力未启用]"})
                    else:
                        content.append(part)
                item["content"] = content
            prepared.append(item)
        window = model.effective_window()
        if not window:
            return prepared

        from .token_budget import estimate
        ratio = getattr(self, 'token_ratios', {}).get(model.id, 1)
        if estimate(prepared, tools) * ratio + reserve > window:
            raise RuntimeError("上下文超过模型窗口；原文未被裁掉，请压缩历史或缩小本次工具结果")
        return prepared
