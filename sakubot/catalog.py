"""On-demand provider model discovery and non-secret model metadata cache."""
import json
import time
from urllib.parse import urlsplit

import httpx

from .config import Capabilities, ModelMetadata


async def read_json(client, url, headers=None, params=None, maximum=20 * 1024 * 1024):
    try:
        async with client.stream("GET", url, headers=headers, params=params) as response:
            if response.status_code != 200:
                raise RuntimeError(f"模型列表获取失败（HTTP {response.status_code}）")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > maximum:
                    raise RuntimeError("模型元数据响应过大")
        return json.loads(data)
    except (httpx.HTTPError, ValueError):
        raise RuntimeError("模型列表获取失败") from None


def metadata_from(record, source):
    nested = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    limit = record.get("limit") if isinstance(record.get("limit"), dict) else {}
    window = next((value for value in (record.get("context_window"), record.get("context_length"),
        record.get("max_context_length"), nested.get("context_window"), limit.get("context"))
        if type(value) is int and 0 < value <= 100000000), 0)
    capabilities = {}
    modalities = record.get("modalities")
    if isinstance(modalities, dict):
        inputs = modalities.get("input")
        outputs = modalities.get("output")
    else:
        architecture = record.get("architecture") or {}
        inputs = record.get("input_modalities") or (architecture.get("input_modalities") if isinstance(architecture, dict) else None)
        outputs = record.get("output_modalities")
    if isinstance(inputs, list):
        capabilities.update(text="text" in inputs, image="image" in inputs, audio="audio" in inputs)
    if isinstance(outputs, list) and "text" not in outputs:
        capabilities["text"] = False
    for key, field in (("vision", "image"), ("tool_call", "tools"), ("supports_tools", "tools")):
        if isinstance(record.get(key), bool):
            capabilities[field] = record[key]
    if isinstance(record.get("capabilities"), dict):
        for field in ("text", "image", "audio", "tools", "embedding"):
            if isinstance(record["capabilities"].get(field), bool):
                capabilities[field] = record["capabilities"][field]
    return ModelMetadata(context_window=window, capabilities=capabilities,
                         source=source if window or capabilities else "", fetched_at=time.time())


class Catalog:
    def __init__(self, config):
        self.config = config

    async def metadata_database(self, client):
        path = self.config.root / "model-metadata.json"
        try:
            saved = json.loads(path.read_text())
        except (OSError, ValueError):
            saved = {}
        if time.time() - saved.get("at", 0) < 86400 and isinstance(saved.get("data"), dict):
            return saved["data"]
        try:
            data = await read_json(client, "https://models.dev/api.json", maximum=64 * 1024 * 1024)
            if not isinstance(data, dict):
                return saved.get("data", {})
            self.config.atomic(path, json.dumps({"at": time.time(), "data": data}, ensure_ascii=False))
            return data
        except RuntimeError:
            return saved.get("data", {})

    @staticmethod
    def lookup(database, provider, identifier):
        candidates = []
        preferred = []
        hostname = urlsplit(provider.api_base).hostname
        prefix, _, suffix = identifier.partition("/")
        for name, info in database.items():
            if not isinstance(info, dict) or not isinstance(info.get("models"), dict):
                continue
            record = info["models"].get(identifier)
            if not record and prefix == name:
                record = info["models"].get(suffix)
            if not isinstance(record, dict):
                continue
            match = metadata_from(record, "models.dev:" + name)
            candidates.append(match)
            if urlsplit(str(info.get("api", ""))).hostname == hostname or prefix == name:
                preferred.append(match)
        choices = preferred or candidates
        if not choices:
            return ModelMetadata()
        # A proxy's model ID can be ambiguous. Never guess the largest context window.
        windows = {item.context_window for item in choices if item.context_window}
        capabilities = {}
        for field in ("text", "image", "audio", "tools"):
            values = {item.capabilities[field] for item in choices if field in item.capabilities}
            if len(values) == 1:
                capabilities[field] = values.pop()
        return ModelMetadata(context_window=windows.pop() if len(windows) == 1 else 0,
            capabilities=capabilities, source=choices[0].source, fetched_at=time.time())

    async def fetch(self, provider):
        rows = []
        seen = set()
        async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
            headers = {"Authorization": "Bearer " + provider.api_key} if provider.api_key else {}
            after = ""
            for _ in range(20):
                params = {"after": after} if after else None
                body = await read_json(client, provider.api_base + "/models", headers, params)
                page = body.get("data") if isinstance(body, dict) else body
                if not isinstance(page, list):
                    raise RuntimeError("供应商未返回标准模型列表")
                for row in page:
                    if isinstance(row, str):
                        row = {"id": row}
                    if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"] not in seen:
                        if len(row["id"]) <= 300:
                            rows.append(row)
                            seen.add(row["id"])
                if not isinstance(body, dict) or not body.get("has_more"):
                    break
                last = body.get("last_id") or (page[-1].get("id") if page and isinstance(page[-1], dict) else None)
                if not isinstance(last, str) or last == after:
                    break
                after = last
            database = await self.metadata_database(client) if rows else {}
        result = []
        for row in rows:
            metadata = metadata_from(row, "provider")
            fallback = self.lookup(database, provider, row["id"])
            if not metadata.context_window:
                metadata.context_window = fallback.context_window
            metadata.capabilities = {**fallback.capabilities, **metadata.capabilities}
            if not metadata.source:
                metadata.source = fallback.source
            result.append({"model_id": row["id"], "name": str(row.get("name") or row["id"])[:100],
                "metadata": metadata.model_dump(),
                "capabilities": Capabilities(**metadata.capabilities).model_dump()})
        return sorted(result, key=lambda row: row["model_id"].casefold())
