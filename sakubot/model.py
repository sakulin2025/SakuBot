import json

import httpx


class Model:
    def __init__(self, settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15), trust_env=False)

    async def close(self):
        await self.client.aclose()

    async def complete(self, messages, tools=None, lightweight=False, model_id=None, output_tokens=None, on_delta=None, on_request=None):
        provider, model = self.settings.selected_model(lightweight, model_id=model_id)
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
            return await self.stream(provider, model, payload, on_delta)
        try:
            response = await self.client.post(provider.api_base + "/chat/completions",
                headers={"Authorization": "Bearer " + provider.api_key} if provider.api_key else {}, json=payload)
        except httpx.HTTPError:
            raise RuntimeError("模型请求失败或超时；没有自动重试") from None
        if response.status_code != 200:
            raise RuntimeError(f"模型接口 HTTP {response.status_code}，请检查模型配置或额度")
        try:
            body = response.json()
            message = body["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError()
            # Preserve reasoning_content for providers which require it on tool turns.
            allowed = ("role", "content", "tool_calls", "reasoning_content")
            result = {key: value for key, value in message.items() if key in allowed}
            result["role"] = "assistant"
            if result.get("tool_calls") and not model.capabilities.tools:
                raise RuntimeError("模型返回了未启用的工具调用")
            if not isinstance(result.get("content"), (str, type(None))):
                result["content"] = json.dumps(result["content"], ensure_ascii=False)
            return result, body.get("usage", {})
        except (KeyError, IndexError, ValueError, TypeError):
            raise RuntimeError("模型接口返回格式不兼容 Chat Completions") from None

    async def stream(self, provider, model, payload, on_delta):
        headers = {"Authorization": "Bearer " + provider.api_key} if provider.api_key else {}
        result = {'role': 'assistant', 'content': ''}
        calls, usage, completed = {}, {}, False

        async def packet(raw):
            nonlocal usage, completed
            if raw.strip() == '[DONE]':
                completed = True
                return
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError()
            if body.get('error'):
                raise RuntimeError('模型流式响应返回错误')
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
                    await on_delta(content)
                reasoning = delta.get('reasoning_content')
                if isinstance(reasoning, str):
                    result['reasoning_content'] = result.get('reasoning_content', '') + reasoning
                for call in delta.get('tool_calls') or []:
                    index = call.get('index', 0)
                    current = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                    if call.get('id'):
                        current['id'] = call['id']
                    function = call.get('function') or {}
                    current['function']['name'] += function.get('name') or ''
                    current['function']['arguments'] += function.get('arguments') or ''

        try:
            async with self.client.stream('POST', provider.api_base + '/chat/completions', headers=headers, json=payload) as response:
                if response.status_code != 200:
                    raise RuntimeError(f'模型接口 HTTP {response.status_code}，请检查模型配置或额度')
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
                raise RuntimeError('模型流式响应中断，没有自动重试')
            if calls:
                if not model.capabilities.tools:
                    raise RuntimeError('模型返回了未启用的工具调用')
                result['tool_calls'] = [calls[index] for index in sorted(calls)]
            return result, usage
        except httpx.HTTPError:
            raise RuntimeError('模型流式请求失败或超时；没有自动重试') from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError('模型流式响应格式不兼容 Chat Completions') from None

    @staticmethod
    def prepare_messages(messages, tools, model, reserve):
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

        def cost():
            # Conservative byte-based token estimate for arbitrary provider tokenizers.
            estimated = []
            for msg in prepared:
                copy = dict(msg)
                if isinstance(copy.get('content'), list):
                    copy['content'] = [{'type': 'image_url', 'image_url': {'url': '<image>'}} if part.get('type') == 'image_url' else part for part in copy['content']]
                estimated.append(copy)
            size = len(json.dumps({"messages": estimated, "tools": tools}, ensure_ascii=False).encode("utf-8"))
            images = sum(1 for msg in prepared if isinstance(msg.get("content"), list)
                         for part in msg["content"] if part.get("type") == "image_url")
            return size + images * 16384 + reserve

        # Preserve the current user event and its entire tool-call chain.
        active = max((index for index, msg in enumerate(messages) if msg.get("role") == "user" and not msg.get('_observation')), default=1)
        prefix = 0
        while prefix < len(prepared) and prepared[prefix].get("role") == "system":
            prefix += 1
        while cost() > window and active > prefix:
            prepared.pop(prefix)
            active -= 1
        if cost() > window:
            raise RuntimeError("当前任务超出模型上下文窗口")
        return prepared
