import uuid
from pathlib import Path

from starlette.background import BackgroundTask
from .components import canonical, required
from .plugin_packages import MAX_ARCHIVE, export_package, import_package, program_path

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse


def register_console_api(app, authorize, config, store, runtime, config_lock):
    auth = [Depends(authorize)]

    @app.api_route('/hooks/{plugin}/{path:path}', methods=['POST'])
    async def plugin_webhook(plugin: str, path: str, request: Request):
        return await runtime.registry.dispatch(plugin, path, request, webhook=True)

    @app.get("/api/plugin-registry", dependencies=auth)
    async def plugin_registry():
        from .plugin import PAGE_GROUPS
        return {"revision": runtime.registry.revision, "pages": runtime.registry.page_manifest(),
            "plugins": runtime.registry.installed_catalog(),
            "page_groups": [{'id': key, 'label': value[0], 'order': value[1], 'builtin_only': key == 'system'} for key, value in PAGE_GROUPS.items()]}

    @app.patch("/api/plugins/{identifier}", dependencies=auth)
    async def toggle_plugin(identifier: str, request: Request):
        data = await request.json()
        await runtime.control.plugins.toggle(identifier, data.get('enabled'))
        return await plugin_registry()

    @app.get('/api/system-control', dependencies=auth)
    async def system_control():
        return runtime.control.status()

    @app.get('/api/system-operations', dependencies=auth)
    async def system_operations():
        return runtime.control.operations.list()

    @app.get('/api/system-operations/{identifier}', dependencies=auth)
    async def system_operation(identifier: str):
        return runtime.control.operations.get(identifier)

    @app.post('/api/system-operations', dependencies=auth)
    async def submit_operation(request: Request):
        data = await request.json()
        return runtime.control.submit(data.get('action'), data.get('payload', {}))

    @app.delete('/api/system-operations/{identifier}', dependencies=auth)
    async def cancel_operation(identifier: str):
        return runtime.control.operations.cancel(identifier)

    @app.get('/api/plugins/{identifier}/settings', dependencies=auth)
    async def plugin_settings(identifier: str):
        from .plugin_settings import public
        return public(runtime, identifier)

    @app.put('/api/plugins/{identifier}/settings', dependencies=auth)
    async def save_plugin_settings(identifier: str, request: Request):
        from .plugin_settings import save
        data = await request.json()
        async with config_lock:
            return await save(runtime, identifier, data)

    @app.post("/api/plugins/{identifier}/reload", dependencies=auth)
    async def reload_plugin(identifier: str):
        await runtime.control.plugins.reload(identifier)
        return await plugin_registry()

    @app.delete("/api/plugins/{identifier}", dependencies=auth)
    async def delete_plugin(identifier: str, purge: bool = Query(False), confirm: bool = Query(False)):
        await runtime.control.plugins.delete(identifier, purge=purge, confirm=confirm)
        return await plugin_registry()

    @app.post('/api/plugin-packages/import', dependencies=auth)
    async def upload_plugin(request: Request, include_data: bool = Query(False)):
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_ARCHIVE:
                raise HTTPException(413, '插件包超过50 MiB')
        async with config_lock:
            result = import_package(config, store, bytes(content), include_data)
            runtime.registry.errors.pop(result['name'], None)
            runtime.registry.revision = uuid.uuid4().hex
        return result

    @app.get('/api/plugins/{identifier}/export', dependencies=auth)
    async def download_plugin(identifier: str, include_data: bool = Query(False)):
        path = await runtime.control.plugins.export_archive(identifier, include_data)
        return FileResponse(path, filename=identifier+'.zip', media_type='application/zip',
            background=BackgroundTask(path.unlink, missing_ok=True))

    @app.api_route("/api/extensions/{plugin}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], dependencies=auth)
    async def plugin_api(plugin: str, path: str, request: Request):
        return await runtime.registry.dispatch(plugin, path, request)

    @app.get("/extensions/{plugin}/{page}")
    async def plugin_redirect(plugin: str, page: str):
        if not runtime.registry.loaded(plugin) or (plugin, page) not in runtime.registry.pages:
            raise HTTPException(404)
        return RedirectResponse(f"/extensions/{plugin}/{page}/")

    @app.get("/extensions/{plugin}/{page}/{asset:path}")
    async def plugin_asset(plugin: str, page: str, asset: str):
        definition = runtime.registry.pages.get((plugin, page))
        if not definition or not runtime.registry.loaded(plugin):
            raise HTTPException(404)
        root = definition["directory"]
        file = (root / (asset or "index.html")).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise HTTPException(404)
        return FileResponse(file, headers={"Cache-Control": "no-cache"})

    @app.get("/api/personas", dependencies=auth)
    async def personas():
        return runtime.personas.list()

    @app.get("/api/personas/{identifier}", dependencies=auth)
    async def persona(identifier: str):
        return runtime.personas.get(identifier)

    @app.post("/api/personas", dependencies=auth)
    async def save_persona(request: Request):
        data = await request.json()
        return runtime.personas.save(data.get("name"), data.get("prompt"), data.get("id", ""),
            **({"visible_plugins": data["visible_plugins"]} if "visible_plugins" in data else {}))

    @app.delete("/api/personas/{identifier}", dependencies=auth)
    async def delete_persona(identifier: str):
        runtime.personas.delete(identifier)
        return {"ok": True}

    @app.get("/api/functions", dependencies=auth)
    async def functions(agent_id: str = "main"):
        return {"items": runtime.function_catalog(agent_id), "model_id": runtime.agents.profile(agent_id)["effective_model_id"],
            "registry_revision": runtime.registry.revision}

    @app.get("/api/logs", dependencies=auth)
    async def logs(before: int = 0, limit: int = Query(100, ge=1, le=200), level: str = "", source: str = "", run_id: str = "", query: str = ""):
        rows = store.rows("""SELECT * FROM logs WHERE id<? AND (?='' OR level=?) AND (?='' OR source=?)
            AND (?='' OR run_id=?) AND instr(event || data,?)>0 ORDER BY id DESC LIMIT ?""",
            (before or 9223372036854775807, level, level, source, source, run_id, run_id, query, limit))
        return {"items": rows, "next_before": rows[-1]["id"] if rows else None}

    @app.get("/api/tool-calls", dependencies=auth)
    async def tool_calls(before: int = 0, limit: int = Query(100, ge=1, le=200), run_id: str = "", plugin_id: str = "", status: str = "", query: str = ""):
        rows = store.rows("""SELECT * FROM tool_calls WHERE id<? AND (?='' OR run_id=?) AND (?='' OR plugin_id=?)
            AND (?='' OR status=?) AND instr(tool_name,?)>0 ORDER BY id DESC LIMIT ?""",
            (before or 9223372036854775807, run_id, run_id, plugin_id, plugin_id, status, status, query, limit))
        return {"items": rows, "next_before": rows[-1]["id"] if rows else None}
