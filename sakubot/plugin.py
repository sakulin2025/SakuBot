import asyncio
import importlib
import importlib.util
import json
import re
import time
import uuid
import sys
from dataclasses import dataclass, field
from pathlib import Path

from starlette.routing import compile_path

import jsonschema
from .store import encode
from .components import SYSTEM_ROOT, BUILTIN_ROOT, required, builtin, canonical, system_ids


@dataclass
class Invocation:
    run_id: str
    target: str
    actor: str = ""
    task_id: str = ""
    call_id: str = ""
    persona_id: str = ""
    agent_id: str = "main"
    model_id: str = ""
    instance: object = None
    control: object = None
    origin: str = "agent"
    metadata: dict = field(default_factory=dict)
    temporary_context: list = field(default_factory=list)
    temporary_next: list = field(default_factory=list)
    send_result_to_source: bool = True
    temporary_tools: dict = field(default_factory=dict)

    def inject_temporary(self, content):
        """Supply a reminder to the next model request of this invocation only."""
        self.temporary_next.extend(temporary_messages(content))


def temporary_messages(content):
    if not isinstance(content, str) or len(content) > 200000:
        raise ValueError('临时上下文必须为文本，最多200000字符')
    return [{'role': 'system', 'content': content}] if content else []


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: object
    plugin_id: str = ""

    def schema(self):
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}


def object_schema(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


def text(description=""):
    return {"type": "string", "description": description}


class Plugin:
    """Trusted local code. setup registers tools; start/stop manage event sources."""
    name = "plugin"

    def __init__(self, runtime):
        self.runtime = runtime
        self.jobs = []
        self.id = self.name

    def availability(self):
        return {"available": True, "reason": ""}

    def prompt_context(self, invocation):
        return ''

    def onboarding(self):
        return []

    def delivery_adapter(self, identifier, handler, *, accepts, availability=None, timeout=30):
        return self.runtime.deliveries.declare(self.id, identifier, handler, accepts, availability or self.availability, timeout)

    @property
    def state(self):
        from .plugin_support import PluginState
        return PluginState(self)

    def artifact(self, path, name=None):
        from .artifacts import publish
        return publish(self, path, name)

    def preview_images(self, invocation, paths, *, note='页面预览'):
        from .artifacts import preview_images
        return preview_images(self, invocation, paths, note)

    def configure(self, defaults=None, *, secrets=()):
        from .plugin_support import PluginConfig
        self._configuration = PluginConfig(self, defaults, secrets)
        return self._configuration

    def settings_form(self, fields, *, validate=None, on_saved=None):
        self._settings_form = {'fields': fields, 'validate': validate, 'on_saved': on_saved}

    def function(self, handler, *, name=None, description=None):
        from .plugin_support import register_function
        return register_function(self, handler, name, description)

    def management(self, title, sections, state, action, *, icon='plugins', order=50):
        from .plugin_support import management
        return management(self, title, sections, state, action, icon=icon, order=order)

    def setup(self):
        pass

    async def start(self):
        pass

    async def stop(self):
        for job in self.jobs:
            job.cancel()
        await asyncio.gather(*self.jobs, return_exceptions=True)

    def background(self, coroutine):
        task = asyncio.ensure_future(coroutine)
        self.jobs.append(task)
        def finished(job):
            if job in self.jobs:
                self.jobs.remove(job)
            if not job.cancelled() and job.exception() is not None:
                self.runtime.store.log('error', self.id, 'plugin.background.failed',
                    data={'error': type(job.exception()).__name__})
        task.add_done_callback(finished)
        return task

    def event_status(self, uid):
        return self.runtime.store.one('SELECT id,uid,kind,status,target,error FROM events WHERE uid=?', (uid,))

    def cancel_wake(self, identifier):
        return self.runtime.cancel_wake(identifier)

    async def emit(self, kind, content, **kwargs):
        return await self.runtime.emit(kind, self.name, content, **kwargs)

    def conversation_source(self, identifier, name, *, handlers=None, availability=None, timeout=30):
        return self.runtime.conversation.declare(self.id, identifier, name, handlers or {}, availability, timeout)

    def remove_conversation_source(self, identifier):
        self.runtime.conversation.remove(self.id, identifier)

    async def receive_main(self, identifier, content, **kwargs):
        return await self.runtime.conversation.receive(self.id, identifier, content, **kwargs)

    async def respond_main(self, parts, *, invocation=None, response_id=None):
        if invocation and invocation.agent_id != 'main':
            raise ValueError('仅主 Agent 可输出主对话响应')
        return await self.runtime.conversation.respond(parts,
            delivery_target=invocation.metadata.get('reply_target', '') if invocation else '',
            send_to_source=invocation.send_result_to_source if invocation else True,
            run_id=invocation.run_id if invocation else '', response_id=response_id)

    def tool(self, name, description, parameters, handler):
        self.runtime.registry.add(Tool(name, description, parameters, handler, plugin_id=self.id))

    def get_agent(self, identifier):
        full_id = identifier if identifier == "main" or ":" in identifier else self.id + ":" + identifier
        return self.runtime.agents.get(full_id, self.id)

    async def reset_agent(self, identifier):
        await self.get_agent(identifier).reset()

    def clear_agent_context(self, identifier):
        self.get_agent(identifier).clear_context()

    def agent(self, identifier, name, description="", *, persona_id="", model_id="", persona_mode=""):
        return self.runtime.agents.declare(self.id, identifier, name, description, persona_id=persona_id, model_id=model_id, persona_mode=persona_mode)

    def set_agents(self, records):
        self.runtime.agents.replace(self.id, records)

    def remove_agent(self, identifier):
        self.runtime.agents.remove(self.id, identifier)

    async def run_agent(self, identifier, goal, *, invocation, context="", run_id=None):
        return await self.runtime.run_agent(self.id + ":" + identifier, goal,
            invocation=invocation, context=context, run_id=run_id)

    def page(self, identifier, title, directory, *, icon="plugins", order=50, aliases=()):
        self.runtime.registry.add_page(self.id, identifier, title, directory, icon, order, aliases)

    def api(self, path, handler, methods=("GET",)):
        self.runtime.registry.add_api(self.id, path, handler, methods)

    @property
    def data_dir(self):
        directory = self.runtime.config.root / 'plugin_data' / self.id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @property
    def personas(self):
        return self.runtime.personas

    @property
    def workspace(self):
        return self.runtime.workspace

    def skill(self, identifier, directory):
        return self.runtime.skills.declare(self.id, identifier, directory)

    def remove_skill(self, identifier):
        self.runtime.skills.declarations.pop(self.id + '.' + identifier, None)
        self.runtime.registry.revision = uuid.uuid4().hex

    async def call_tool(self, name, arguments):
        invocation = Invocation("dashboard:" + uuid.uuid4().hex, self.runtime.main_target(),
            actor="owner", call_id=uuid.uuid4().hex, origin="dashboard")
        return await self.runtime.registry.call(name, arguments, invocation)


class Registry:
    def __init__(self):
        self.tools = {}
        self.plugins = []
        self.pages = {}
        self.apis = []
        self.runtime = None
        self.inflight = {}
        self.errors = {}
        self.revision = uuid.uuid4().hex

    def loaded(self, identifier):
        return any(plugin.id == identifier for plugin in self.plugins)

    def availability(self, identifier):
        plugin = next((item for item in self.plugins if item.id == identifier), None)
        if plugin is None:
            return {"available": False, "state": "unavailable" if identifier in self.errors else "disabled", "reason": self.errors.get(identifier, "")}
        try:
            from .plugin_settings import declaration, configuration, missing
            spec = declaration(self.runtime, identifier)
            if spec and missing(spec, configuration(self.runtime, identifier, spec)[0]):
                return {"available": False, "state": "pending_configuration", "reason": "请完成插件设置"}
            status = plugin.availability()
            available = bool(status.get('available', True))
            return {"available": available, "state": "enabled" if available else "unavailable", "reason": str(status.get('reason', ''))[:300]}
        except Exception:
            return {"available": False, "state": "unavailable", "reason": "插件状态获取失败"}

    def onboarding(self):
        return [dict(step, plugin_id=plugin.id, optional=True) for plugin in self.plugins for step in plugin.onboarding()]

    def add_page(self, plugin, identifier, title, directory, icon, order, aliases):
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,40}", identifier) or any(owner == plugin for owner, _ in self.pages):
            raise ValueError("每个插件最多声明一个页面，且页面 ID 必须有效")
        if any(not alias.startswith("/") or alias.startswith("//") for alias in aliases):
            raise ValueError("插件页面别名无效")
        self.pages[(plugin, identifier)] = {"plugin_id": plugin, "id": identifier, "title": title,
            "directory": Path(directory).resolve(), "group": "系统" if builtin(plugin) else "插件", "icon": icon, "order": order,
            "group_order": 90 if builtin(plugin) else 100, "aliases": list(aliases),
            "route": f"/extensions/{plugin}/{identifier}", "url": f"/extensions/{plugin}/{identifier}/"}

    def page_manifest(self):
        return [{key: value for key, value in page.items() if key != "directory"}
            for page in self.pages.values() if self.loaded(page["plugin_id"])]

    def add_api(self, plugin, path, handler, methods):
        path = "/" + path.strip("/")
        if any(row["plugin_id"] == plugin and row["path"] == path and row["methods"] & set(methods) for row in self.apis):
            raise ValueError("插件 API 路径重复")
        regex, _, converters = compile_path(path)
        self.apis.append({"plugin_id": plugin, "path": path, "regex": regex,
            "converters": converters, "methods": set(methods), "handler": handler})

    async def dispatch(self, plugin, path, request):
        from fastapi import HTTPException
        if not self.loaded(plugin):
            raise HTTPException(404, "插件未启用")
        for api in self.apis:
            if api["plugin_id"] == plugin and request.method in api["methods"]:
                match = api["regex"].fullmatch("/" + path.strip("/"))
                if match:
                    request.path_params.update({key: api["converters"][key].convert(value) for key, value in match.groupdict().items()})
                    return await api["handler"](request)
        raise HTTPException(404, "插件接口不存在")

    def add(self, tool):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", tool.name) or tool.name in self.tools:
            raise ValueError(f"工具名称无效或重复：{tool.name}")
        jsonschema.Draft202012Validator.check_schema(tool.parameters)
        self.tools[tool.name] = tool

    def visible_plugin_ids(self, inv):
        if inv.origin == "dashboard":
            return {plugin.id for plugin in self.plugins if self.availability(plugin.id)["available"]}
        profile = inv.metadata.get("agent_profile")
        selected = profile["_visible_plugins"] if profile else self.runtime.agents.visible_plugins(inv.agent_id)
        return {plugin.id for plugin in self.plugins if (required(plugin.id) or selected is None or plugin.id in selected) and self.availability(plugin.id)["available"]}

    def available(self, inv):
        if inv.instance:
            inv.instance.ensure_active()
        visible = self.visible_plugin_ids(inv)
        tools = dict(self.tools)
        if inv.instance and inv.instance.active:
            for name, tool in inv.instance.tools.items():
                if name in tools:
                    raise ValueError("Agent 临时函数与插件函数重名：" + name)
                tools[name] = tool
        available = [tool for tool in tools.values() if tool.plugin_id in visible]
        for name, tool in inv.temporary_tools.items():
            if name in tools:
                raise ValueError('本轮临时函数与其他函数重名：' + name)
            available.append(tool)
        return available

    async def call(self, name, arguments, inv):
        store = self.runtime.store
        known = inv.temporary_tools.get(name) or (inv.instance.tools.get(name) if inv.instance else None) or self.tools.get(name)
        last = (inv.metadata.get("function_snapshots") or [{}])[-1]
        plugin = known.plugin_id if known else next((row["plugin_id"] for row in last.get("functions", []) if row["function"]["name"] == name), "")
        raw = arguments if isinstance(arguments, str) else encode(arguments)
        trace_id = store.execute("""INSERT INTO tool_calls
          (run_id,call_id,tool_name,plugin_id,origin,arguments,status,started)
          VALUES (?,?,?,?,?,?,'running',?)""", (inv.run_id, inv.call_id, name, plugin, inv.origin, raw, time.time())).lastrowid
        store.log("info", plugin or "registry", "tool.started", run_id=inv.run_id, tool_call_id=trace_id, data={"function": name})
        task = None
        try:
            tools = {tool.name: tool for tool in self.available(inv)}
            if name not in tools:
                raise ValueError("函数不存在或当前人格不可见")
            tool = tools[name]
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            jsonschema.validate(args, tool.parameters)
            if inv.instance:
                await inv.instance.dispatch("tool_call", {"run_id": inv.run_id, "phase": "before", "name": name, "arguments": args, "invocation": inv})
            self.runtime.conversation.process('tool.started', run_id=inv.run_id, call_id=inv.call_id, agent_id=inv.agent_id, name=name, arguments=args)
            task = asyncio.create_task(tool.handler(inv, args))
            self.inflight.setdefault(plugin, set()).add(task)
            result = await task
            output = encode(result)
            if len(output) > 1000000:
                output = encode({"truncated": True, "preview": output[:1000000]})
            store.execute("UPDATE tool_calls SET output=?,status='done',finished=? WHERE id=?", (output, time.time(), trace_id))
            store.log("info", plugin, "tool.completed", run_id=inv.run_id, tool_call_id=trace_id, data={"function": name})
            if inv.instance:
                await inv.instance.dispatch("tool_call", {"run_id": inv.run_id, "phase": "after", "name": name, "result": result, "invocation": inv})
            self.runtime.conversation.process('tool.completed', run_id=inv.run_id, call_id=inv.call_id, agent_id=inv.agent_id, name=name, output=output[:20000])
            return result
        except BaseException as exc:
            cancelled = isinstance(exc, asyncio.CancelledError)
            error = "操作被中断，远端结果可能未知" if cancelled else (str(exc)[:500] if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__)
            store.execute("UPDATE tool_calls SET status=?,finished=?,error=? WHERE id=?",
                ("interrupted" if cancelled else "failed", time.time(), error, trace_id))
            store.log("warning" if cancelled else "error", plugin or "registry", "tool.interrupted" if cancelled else "tool.failed",
                run_id=inv.run_id, tool_call_id=trace_id, data={"function": name, "error": error})
            if inv.instance:
                await inv.instance.dispatch("tool_call", {"run_id": inv.run_id, "phase": "error", "name": name, "error": error, "invocation": inv})
            self.runtime.conversation.process('tool.failed', run_id=inv.run_id, call_id=inv.call_id, agent_id=inv.agent_id, name=name, error=error)
            if cancelled and not asyncio.current_task().cancelling():
                raise RuntimeError("插件已停用，操作结果可能未知") from None
            raise
        finally:
            if task:
                self.inflight.get(plugin, set()).discard(task)

    async def load(self, runtime):
        self.runtime = runtime
        for name in [*system_ids(), *runtime.config.settings.plugins]:
            try:
                await self.enable(name)
            except Exception as exc:
                self.errors[name] = '加载失败（' + type(exc).__name__ + '）'
                runtime.store.log('error', name, 'plugin.failed', data={'error': type(exc).__name__})
                if required(name):
                    raise RuntimeError('系统基础能力加载失败：' + name) from exc

    def remove_entries(self, identifier):
        self.runtime.deliveries.remove_owner(identifier)
        self.runtime.conversation.remove_owner(identifier)
        self.runtime.skills.remove_owner(identifier)
        self.runtime.agents.remove(identifier)
        self.tools = {name: tool for name, tool in self.tools.items() if tool.plugin_id != identifier}
        self.pages = {key: page for key, page in self.pages.items() if page["plugin_id"] != identifier}
        self.apis = [api for api in self.apis if api["plugin_id"] != identifier]
        self.revision = uuid.uuid4().hex

    async def enable(self, name, start=False):
        name = canonical(name)
        if self.loaded(name):
            return
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", name):
            raise ValueError("插件名称无效")
        if required(name):
            module = importlib.import_module("sakubot.system." + name)
        elif (BUILTIN_ROOT / name / "__init__.py").is_file():
            module = importlib.import_module("sakubot.plugins." + name)
        else:
            dependencies = self.runtime.config.root / 'plugin_dependencies'
            if str(dependencies) not in sys.path:
                sys.path.insert(0, str(dependencies))
            prefix = 'sakubot_extension_' + name
            for key in list(sys.modules):
                if key == prefix or key.startswith(prefix + '.'):
                    del sys.modules[key]
            importlib.invalidate_caches()
            package = self.runtime.config.root / "plugins" / name
            path = package / "__init__.py" if package.is_dir() else self.runtime.config.root / "plugins" / (name + ".py")
            spec = importlib.util.spec_from_file_location("sakubot_extension_" + name, path,
                submodule_search_locations=[str(package)] if package.is_dir() else None)
            if not spec or not spec.loader:
                raise ValueError("无法加载插件")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        plugin = module.Extension(self.runtime)
        plugin.id = name
        try:
            plugin.setup()
            if hasattr(module, '__path__'):
                self.runtime.skills.discover(name, Path(module.__file__).parent)
            if start:
                await plugin.start()
            self.plugins.append(plugin)
            self.errors.pop(name, None)
            self.revision = uuid.uuid4().hex
            self.runtime.store.log("info", name, "plugin.enabled")
        except BaseException:
            self.remove_entries(name)
            await plugin.stop()
            raise

    async def disable(self, identifier, internal=False):
        identifier = canonical(identifier)
        if required(identifier) and not internal:
            raise ValueError('基础能力不能停用')
        plugin = next((item for item in self.plugins if item.id == identifier), None)
        if not plugin:
            return
        owned = {task for instance in self.runtime.agents.instances.values()
            for task, owner in instance.tasks.items() if owner == identifier or instance.id.startswith(identifier + ":")}
        self.plugins.remove(plugin)
        self.remove_entries(identifier)
        tasks = list(set(self.inflight.get(identifier, set())) | owned)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await plugin.stop()
        self.runtime.store.log("info", identifier, "plugin.disabled")

    async def reload(self, identifier):
        await self.disable(identifier, internal=True)
        module_name = ("sakubot.system." if required(identifier) else "sakubot.plugins.") + identifier
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        await self.enable(identifier, start=self.runtime.sources_started)

    def installed_catalog(self):
        definitions = {}
        for root in (SYSTEM_ROOT, BUILTIN_ROOT, self.runtime.config.root / "plugins"):
            if not root.is_dir():
                continue
            for path in sorted(root.iterdir()):
                name = path.name if path.is_dir() else path.stem
                if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", name):
                    continue
                if path.is_dir() and not (path / "__init__.py").is_file():
                    continue
                if path.is_file() and path.suffix != ".py":
                    continue
                manifest = path / "plugin.json" if path.is_dir() else path.with_suffix(".json")
                try:
                    metadata = json.loads(manifest.read_text()) if manifest.is_file() else {}
                except (OSError, ValueError):
                    metadata = {}
                if name in definitions:
                    continue
                definitions[name] = {"builtin": root in (SYSTEM_ROOT, BUILTIN_ROOT), "name": name, "label": str(metadata.get("label") or name),
                    "required": root == SYSTEM_ROOT, **self.availability(name), "icon": str(metadata.get("icon") or "plugins"),
                    "selected": root == SYSTEM_ROOT or name in self.runtime.config.settings.plugins, "loaded": self.loaded(name)}
        from .plugin_settings import declaration, configuration, missing
        for item in definitions.values():
            spec = declaration(self.runtime, item['name']) if not item['builtin'] else None
            item['has_settings'] = bool(spec)
            item['configured'] = not spec or not missing(spec, configuration(self.runtime, item['name'], spec)[0])
            if spec and not item['configured'] and item['name'] not in self.errors:
                item['state'] = 'pending_configuration'
                item['reason'] = '请完成插件设置'
        return list(definitions.values())

    async def start(self):
        for plugin in list(self.plugins):
            try:
                await plugin.start()
            except Exception as exc:
                await self.disable(plugin.id, internal=True)
                self.errors[plugin.id] = '启动失败（' + type(exc).__name__ + '）'
                self.runtime.store.log('error', plugin.id, 'plugin.failed', data={'error': type(exc).__name__})
                if required(plugin.id):
                    raise RuntimeError('系统基础能力启动失败：' + plugin.id) from exc

    async def stop(self):
        for plugin in reversed(self.plugins):
            self.remove_entries(plugin.id)
            await plugin.stop()
        self.plugins.clear()
