from fastapi import Depends, Request
from pydantic import ValidationError

from .config import AgentPreferences


def register_agent_api(app, authorize, config, store, runtime, config_lock):
    auth = [Depends(authorize)]

    def response():
        settings = config.settings
        return {"revision": runtime.agents.revision,
            "defaults": {"persona_id": settings.main_persona_id, "model_id": settings.main_model_id},
            "items": runtime.agents.list()}

    @app.get("/api/agents", dependencies=auth)
    async def agents():
        return response()

    async def save(identifier, data):
        fields = {"persona_id", "model_id"}
        if not isinstance(data, dict) or set(data) - fields:
            raise ValueError("Agent 配置字段无效")
        async with config_lock:
            if identifier is not None:
                declaration = runtime.agents.raw(identifier)
                if declaration.get('persona_mode') == 'managed' and 'persona_id' in data:
                    raise ValueError('人格由插件自管理')
            draft = config.settings.model_copy(deep=True)
            if identifier is None:
                base = {"persona_id": draft.main_persona_id, "model_id": draft.main_model_id}
            else:
                base = draft.agent_settings.get(identifier, AgentPreferences()).model_dump()
            try:
                prefs = AgentPreferences.model_validate({**base, **data})
            except ValidationError:
                raise ValueError("Agent 配置无效") from None
            if identifier is not None and declaration.get('persona_mode') == 'managed':
                prefs.persona_id = ''
            if prefs.persona_id:
                runtime.personas.get(prefs.persona_id)
            elif identifier is None:
                raise ValueError("请选择默认人格")
            if prefs.model_id and draft.selected_model(model_id=prefs.model_id)[0] is None:
                raise ValueError("请选择已启用的文本模型")
            if identifier is None:
                draft.main_persona_id, draft.main_model_id = prefs.persona_id, prefs.model_id
            else:
                draft.agent_settings[identifier] = prefs
            if draft.enabled and not draft.ready():
                draft.enabled = False
            config.save(draft)
            runtime.model.settings = draft
            runtime.agents.changed()
            await runtime.sync_main_worker()
            store.log("info", "agents", "agent.configured", data={"agent_id": identifier or "defaults"})
        return response()

    @app.patch("/api/agent-defaults", dependencies=auth)
    async def defaults(request: Request):
        return await save(None, await request.json())

    @app.patch("/api/agents/{identifier}", dependencies=auth)
    async def preferences(identifier: str, request: Request):
        return await save(identifier, await request.json())

    @app.patch("/api/agents/main/state", dependencies=auth)
    async def main_state(request: Request):
        data = await request.json()
        async with config_lock:
            await runtime.set_main_enabled(data.get("enabled"))
        return response()

    @app.post("/api/agents/{identifier}/clear-context", dependencies=auth)
    async def clear_context(identifier: str):
        runtime.agents.raw(identifier)
        runtime.agents.get(identifier).clear_context()
        return response()

    @app.post("/api/agents/{identifier}/reset", dependencies=auth)
    async def reset_agent(identifier: str):
        runtime.agents.raw(identifier)
        await runtime.agents.get(identifier).reset()
        return response()
