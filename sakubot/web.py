import asyncio
import json
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import __version__
from .config import Config, Settings
from .model_api import register_model_api
from .console_api import register_console_api
from .agent_api import register_agent_api
from .skill_api import register_skill_api
from .chat import register_chat_api
from .runtime import Runtime
from .store import Store


config = Config()
store = Store(config.root)
runtime = Runtime(config, store)
config_lock = asyncio.Lock()
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app):
    await runtime.start()
    print("SakuBot " + __version__ + " 已启动；管理令牌保存在 /data/admin_token。", flush=True)
    try:
        yield
    finally:
        await runtime.stop()
        store.db.close()


app = FastAPI(title="SakuBot", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)


async def authorize(authorization: str = Header(default="")):
    if not secrets.compare_digest(authorization, "Bearer " + config.token):
        raise HTTPException(401, "管理令牌不正确")


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    if request.url.path.startswith("/extensions/"):
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)[:500]})


@app.exception_handler(RuntimeError)
async def runtime_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)[:500]})


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/api/status", dependencies=[Depends(authorize)])
async def status():
    return {"version": __version__, **runtime.status()}


@app.post('/api/chat/clear-context', dependencies=[Depends(authorize)])
async def clear_main_context(request: Request):
    data = await request.json()
    if not isinstance(data, dict) or data.get('confirmation') != '清除':
        raise ValueError('请输入清除以确认操作')
    async with config_lock:
        try:
            return runtime.clear_main_context()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None


@app.get("/api/config", dependencies=[Depends(authorize)])
async def get_config():
    return config.public()


@app.patch("/api/admin-token", dependencies=[Depends(authorize)])
async def change_admin_token(request: Request):
    data = await request.json()
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not 1 <= len(token) <= 256 or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise ValueError("令牌格式不正确")
    async with config_lock:
        config.atomic(config.root / "admin_token", token + "\n")
        config.token = token
        store.log("info", "console", "admin_token.changed")
    return {"ok": True}


@app.put("/api/config", dependencies=[Depends(authorize)])
async def put_config(request: Request):
    draft = await request.json()
    return await apply_config(draft)


async def apply_config(draft):
    if not isinstance(draft, dict):
        raise ValueError("配置必须为对象")
    for provider in draft.get("providers", []):
        old = next((item for item in config.settings.providers if item.id == provider.get("id")), None)
        if old and not provider.get("api_key"):
            provider["api_key"] = old.api_key
    try:
        settings = Settings.model_validate(draft)
    except ValidationError:
        # Pydantic errors can contain secret input values; do not echo them.
        raise ValueError("配置格式不正确，请检查地址、模式、数值范围及插件名称") from None
    runtime.personas.get(settings.main_persona_id)
    if settings.message_processing.image_model_id:
        _, image_model = settings.selected_model(model_id=settings.message_processing.image_model_id)
        if image_model is None or not image_model.capabilities.image:
            raise ValueError("请选择支持图片的已启用模型")
    async with config_lock:
        previous = config.settings
        await runtime.stop()
        try:
            config.save(settings)
            await runtime.start(strict=True)
        except Exception:
            await runtime.stop()
            config.save(previous)
            await runtime.start()
            raise ValueError("配置或插件无法加载，已恢复原配置；请检查本地插件代码") from None
    return {"ok": True, "config": config.public()}


@app.patch("/api/config", dependencies=[Depends(authorize)])
async def patch_config(request: Request):
    data = await request.json()
    fields = {
        "model": {"main_model_id", "lightweight_model_id"},
        "runtime": {"enabled"},
        "conversation": {"conversation"},
        "message_processing": {"message_processing"},
        "settings": {"main_persona_id", "max_steps", "context_chars", "agent_concurrency", "compression_enabled", "compression_threshold", "message_processing", "conversation"},
    }
    section = data.get("section")
    values = data.get("values")
    if section not in fields or not isinstance(values, dict) or set(values) - fields[section]:
        raise ValueError("配置字段不正确")
    if section == 'conversation':
        async with config_lock:
            settings = Settings.model_validate({**config.settings.model_dump(), **values})
            config.save(settings)
            runtime.model.settings = settings
            runtime.live.publish('conversation.settings', **settings.conversation.model_dump())
        return {'ok': True, 'config': config.public()}
    if section == "runtime":
        async with config_lock:
            await runtime.set_main_enabled(values.get("enabled"))
        return {"ok": True, "config": config.public()}
    result = await apply_config({**config.settings.model_dump(), **values})
    reviewed = store.kv_get("console_setup", {})
    reviewed[section] = True
    store.kv_set("console_setup", reviewed)
    return result


@app.get("/api/setup", dependencies=[Depends(authorize)])
async def setup():
    settings = config.settings
    return {
        "completed": {
            "model": settings.model_ready(),
            "persona": any(item["id"] == runtime.agents.profile("main")["effective_persona_id"] for item in runtime.personas.list()),
            "plugins": bool(runtime.registry.plugins),
        },
        "optional": ["plugins"],
        "steps": runtime.registry.onboarding(),
        "plugins": runtime.registry.installed_catalog(),
    }


@app.get("/api/events", dependencies=[Depends(authorize)])
async def events(before: int = 0, limit: int = Query(50, ge=1, le=100), status: str = "", query: str = "", kind: str = ""):
    rows = store.rows("""SELECT * FROM events WHERE id<? AND (?='' OR status=?)
      AND instr(text,?)>0 AND (?='' OR kind=?) ORDER BY id DESC LIMIT ?""",
      (before or 9223372036854775807, status, status, query, kind, kind, limit))
    return {"items": rows, "next_before": rows[-1]["id"] if rows else None}


@app.post("/api/events", dependencies=[Depends(authorize)])
async def emit_event(request: Request):
    data = await request.json()
    return await runtime.emit(data.get("kind", "context"), "dashboard", data.get("text", ""),
        actor="owner", label="管理页面",
        target=data.get("target") or runtime.main_target(), include_context=bool(data.get("include_context")),
        temporary_context=data.get("temporary_context", ""), priority=100)


@app.post("/api/events/{identifier}/cancel", dependencies=[Depends(authorize)])
async def cancel_event(identifier: int):
    return runtime.cancel_wake(identifier)


@app.get("/api/runs", dependencies=[Depends(authorize)])
async def runs():
    return store.rows("SELECT id,event_id,started,finished,status,error FROM runs ORDER BY started DESC LIMIT 100")


@app.get("/api/runs/{identifier}", dependencies=[Depends(authorize)])
async def run(identifier: str):
    row = store.one("SELECT * FROM runs WHERE id=?", (identifier,))
    if not row:
        raise HTTPException(404, "运行不存在")
    row["tool_calls"] = store.rows("SELECT * FROM tool_calls WHERE run_id=? ORDER BY id", (identifier,))
    return row


@app.get("/api/deliveries", dependencies=[Depends(authorize)])
async def deliveries():
    return store.rows("SELECT * FROM deliveries ORDER BY at DESC LIMIT 100")


register_model_api(app, authorize, config, store, runtime, config_lock, apply_config)

register_console_api(app, authorize, config, store, runtime, config_lock)

register_agent_api(app, authorize, config, store, runtime, config_lock)

register_skill_api(app, authorize, runtime)

register_chat_api(app, authorize, runtime, config)

from .artifacts import register_artifacts
register_artifacts(app, runtime)
