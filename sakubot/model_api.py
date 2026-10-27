import hashlib
import json
import time

from fastapi import Depends, HTTPException, Request
from pydantic import ValidationError

from .catalog import Catalog
from .config import ModelConfig, ProviderConfig


def signature(provider):
    return hashlib.sha256(json.dumps([provider.api_base, provider.api_key]).encode()).hexdigest()


def register_model_api(app, authorize, config, store, runtime, config_lock, apply_config):
    dependencies = [Depends(authorize)]

    def provider_by_id(identifier):
        provider = next((item for item in config.settings.providers if item.id == identifier), None)
        if not provider:
            raise HTTPException(404, "供应商不存在")
        return provider

    def cached(provider):
        data = store.kv_get("provider-models:" + provider.id, {})
        return data if data.get("signature") == signature(provider) else {"items": [], "fetched_at": 0}

    async def save_catalog(draft):
        valid_ids = {item["id"] for item in draft["models"]}
        for field in ("main_model_id", "lightweight_model_id"):
            if draft[field] not in valid_ids:
                draft[field] = ""
        selected = next((item for item in draft["models"] if item["id"] == draft["main_model_id"]), None)
        provider = next((item for item in draft["providers"] if selected and item["id"] == selected["provider_id"]), None)
        if not selected or not selected["enabled"] or not selected["capabilities"]["text"] or not provider or not provider["enabled"]:
            draft["main_model_id"] = ""
        from .config import Settings
        if not Settings.model_validate(draft).model_ready():
            draft["enabled"] = False
        light = next((item for item in draft["models"] if item["id"] == draft["lightweight_model_id"]), None)
        light_provider = next((item for item in draft["providers"] if light and item["id"] == light["provider_id"]), None)
        if not light or not light["enabled"] or not light["capabilities"]["text"] or not light_provider or not light_provider["enabled"]:
            draft["lightweight_model_id"] = ""
        image_id = draft.get("message_processing", {}).get("image_model_id", "")
        image = next((item for item in draft["models"] if item["id"] == image_id), None)
        image_provider = next((item for item in draft["providers"] if image and item["id"] == image["provider_id"]), None)
        if image_id and (not image or not image["enabled"] or not image["capabilities"]["image"] or not image_provider or not image_provider["enabled"]):
            draft["message_processing"]["image_model_id"] = ""
        return await apply_config(draft)

    @app.get("/api/model-catalog", dependencies=dependencies)
    async def catalog():
        data = config.public()
        return {key: data[key] for key in ("providers", "models", "main_model_id", "lightweight_model_id")}

    @app.post("/api/providers", dependencies=dependencies)
    async def save_provider(request: Request):
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("供应商配置不正确")
        identifier = data.get("id")
        old = provider_by_id(identifier) if identifier else None
        if old and not data.get("api_key"):
            data["api_key"] = old.api_key
        try:
            record = ProviderConfig.model_validate(data)
        except ValidationError:
            raise ValueError("供应商配置不正确") from None
        draft = config.settings.model_dump()
        draft["providers"] = [row for row in draft["providers"] if row["id"] != record.id] + [record.model_dump()]
        await save_catalog(draft)
        return {"id": record.id}

    @app.delete("/api/providers/{identifier}", dependencies=dependencies)
    async def delete_provider(identifier: str):
        provider_by_id(identifier)
        draft = config.settings.model_dump()
        draft["providers"] = [row for row in draft["providers"] if row["id"] != identifier]
        draft["models"] = [row for row in draft["models"] if row["provider_id"] != identifier]
        return await save_catalog(draft)

    @app.get("/api/providers/{identifier}/models", dependencies=dependencies)
    async def available_models(identifier: str):
        data = cached(provider_by_id(identifier))
        return {"items": data["items"], "fetched_at": data["fetched_at"]}

    @app.post("/api/providers/{identifier}/models/fetch", dependencies=dependencies)
    async def fetch_models(identifier: str):
        provider = provider_by_id(identifier)
        original = signature(provider)
        items = await Catalog(config).fetch(provider)
        async with config_lock:
            if signature(provider_by_id(identifier)) != original:
                raise RuntimeError("供应商配置已变更")
            store.kv_set("provider-models:" + identifier, {"items": items, "fetched_at": time.time(), "signature": original})
            # Metadata refresh does not restart/cancel running conversations.
            metadata = {row["model_id"]: row["metadata"] for row in items}
            settings = config.settings.model_copy(deep=True)
            for model in settings.models:
                if model.provider_id == identifier and model.model_id in metadata:
                    model.metadata = type(model.metadata).model_validate(metadata[model.model_id])
            config.save(settings)
            if runtime.model:
                runtime.model.settings = settings
        return {"items": items, "fetched_at": time.time()}

    @app.post("/api/models", dependencies=dependencies)
    async def save_model(request: Request):
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("模型配置不正确")
        provider = provider_by_id(data.get("provider_id"))
        old = next((item for item in config.settings.models if item.id == data.get("id")), None)
        if data.get("id") and not old:
            raise HTTPException(404, "模型不存在")
        match = next((item for item in cached(provider)["items"] if item["model_id"] == data.get("model_id")), None)
        data["metadata"] = match["metadata"] if match else (old.metadata.model_dump() if old and old.model_id == data.get("model_id") and old.provider_id == provider.id else {})
        try:
            record = ModelConfig.model_validate(data)
        except ValidationError:
            raise ValueError("模型配置不正确") from None
        draft = config.settings.model_dump()
        draft["models"] = [row for row in draft["models"] if row["id"] != record.id] + [record.model_dump()]
        await save_catalog(draft)
        return {"id": record.id}

    @app.post("/api/models/import", dependencies=dependencies)
    async def import_models(request: Request):
        data = await request.json()
        provider = provider_by_id(data.get("provider_id"))
        identifiers = data.get("model_ids")
        if not isinstance(identifiers, list) or len(identifiers) > 1000 or not all(isinstance(item, str) for item in identifiers):
            raise ValueError("模型列表不正确")
        available = {row["model_id"]: row for row in cached(provider)["items"]}
        draft = config.settings.model_dump()
        existing = {row["model_id"] for row in draft["models"] if row["provider_id"] == provider.id}
        added = []
        for identifier in dict.fromkeys(identifiers):
            if identifier in existing:
                continue
            row = available.get(identifier)
            if not row:
                raise ValueError("请重新拉取供应商模型列表")
            record = ModelConfig(provider_id=provider.id, model_id=identifier, name=row["name"],
                                 capabilities=row["capabilities"], metadata=row["metadata"])
            draft["models"].append(record.model_dump())
            added.append(record.id)
        await save_catalog(draft)
        return {"added": added}

    @app.delete("/api/models/{identifier}", dependencies=dependencies)
    async def delete_model(identifier: str):
        draft = config.settings.model_dump()
        draft["models"] = [row for row in draft["models"] if row["id"] != identifier]
        return await save_catalog(draft)
