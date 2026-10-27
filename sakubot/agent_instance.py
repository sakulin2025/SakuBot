import asyncio
import copy
import inspect
import re
import time
import uuid
from contextvars import ContextVar

import jsonschema

from .plugin import Invocation, Tool, temporary_messages
from .personas import managed_persona
from .store import encode


_CURRENT_AGENT = ContextVar("sakubot_current_agent", default=None)


class AgentInvalidatedError(RuntimeError):
    pass


class AgentRunControl:
    def __init__(self, instance, invocation, deadline):
        self.instance, self.invocation, self.deadline = instance, invocation, deadline
        self.slot_held = True
        self.waiting = False

    async def wait_for(self, future):
        self.instance.ensure_active()
        if self.waiting:
            raise ValueError("Agent 已在等待输入")
        loop = asyncio.get_running_loop()
        remaining = max(0, self.deadline.when() - loop.time()) if self.deadline.when() is not None else None
        self.deadline.reschedule(None)
        self.waiting = True
        if self.slot_held:
            self.instance.runtime.agent_slots.release()
            self.slot_held = False
        store = self.instance.runtime.store
        store.execute("UPDATE runs SET status='waiting' WHERE id=? AND status='running'", (self.invocation.run_id,))

        async def resume():
            self.instance.ensure_active()
            await self.instance.runtime.agent_slots.acquire()
            self.slot_held = True
            if remaining is not None:
                self.deadline.reschedule(loop.time() + remaining)
            store.execute("UPDATE runs SET status='running' WHERE id=? AND status='waiting'", (self.invocation.run_id,))
            await self.instance.dispatch("resumed", {"run_id": self.invocation.run_id, "invocation": self.invocation})

        try:
            await self.instance.dispatch("waiting", {"run_id": self.invocation.run_id, "invocation": self.invocation})
            try:
                result = await future
            except Exception:
                await resume()
                raise
            await resume()
            return result
        finally:
            self.waiting = False


class AgentHandle:
    def __init__(self, instance, owner):
        self._instance, self.owner, self._valid = instance, owner, True

    @property
    def instance(self):
        if not self._valid:
            raise AgentInvalidatedError("插件已卸载，Agent 引用已失效")
        self._instance.ensure_active()
        return self._instance

    @property
    def id(self):
        return self.instance.id

    @property
    def instance_id(self):
        return self.instance.generation

    def set_persona(self, prompt):
        instance = self.instance
        instance.ensure_managed()
        instance.managed_prompt = managed_persona(prompt)['prompt']
        instance.service.changed()
        return self

    def with_plugins(self, identifiers=None):
        instance = self.instance
        instance.ensure_managed()
        instance.managed_plugins = managed_persona('validate', identifiers)['visible_plugins']
        instance.service.changed()
        return self

    def with_plugin(self, identifier):
        instance = self.instance
        instance.ensure_managed()
        return self.with_plugins([*(instance.managed_plugins or []), identifier])

    def tool(self, name, description, parameters, handler):
        instance = self.instance
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
            raise ValueError("函数名无效")
        existing = instance.tools.get(name)
        if existing and existing.plugin_id != self.owner:
            raise ValueError("临时函数名称重复")
        jsonschema.Draft202012Validator.check_schema(parameters)
        instance.tools[name] = Tool(name, description, parameters, handler, plugin_id=self.owner)
        return self

    def inject(self, content, role="user", *, temporary=False):
        instance = self.instance
        if instance.resetting:
            raise RuntimeError("Agent 正在重置")
        if role not in ("user", "assistant") or not isinstance(content, str) or len(content) > 200000:
            raise ValueError("上下文无效")
        instance.pending.append({"owner": self.owner, "role": role, "content": content, "_temporary": temporary})
        instance.save_pending()
        return self

    def on(self, event, callback):
        instance = self.instance
        if event not in {"started", "model_request", "tool_call", "tool_round", "completed", "failed", "cancelled", "compressed", "waiting", "resumed", "reset"}:
            raise ValueError("生命周期事件无效")
        entry = (self.owner, callback)
        if entry not in instance.callbacks.setdefault(event, []):
            instance.callbacks[event].append(entry)
        def unsubscribe():
            current = self.instance
            if entry in current.callbacks.get(event, []):
                current.callbacks[event].remove(entry)
        return unsubscribe

    def wake(self, goal="", **kwargs):
        instance = self.instance
        if instance.resetting:
            raise RuntimeError("Agent 正在重置")
        injected = instance.take_pending(self.owner)
        task = asyncio.create_task(instance.run(goal, _injected=injected, **kwargs), name="agent:" + instance.id)
        instance.tasks[task] = self.owner
        def finished(job):
            instance.tasks.pop(job, None)
            if not job.cancelled():
                job.exception()
        task.add_done_callback(finished)
        return task

    def clear_context(self):
        self.instance.clear_context()

    async def reset(self):
        await self.instance.reset()

    async def wait_for(self, future, *, invocation):
        instance = self.instance
        if invocation.instance is not instance or invocation.control is None:
            raise ValueError("运行实例不匹配")
        return await invocation.control.wait_for(future)


class AgentInstance:
    def __init__(self, service, identifier):
        self.service, self.runtime, self.id = service, service.runtime, identifier
        self.tools, self.callbacks, self.tasks, self.handles = {}, {}, {}, {}
        self.lock, self.reset_lock = asyncio.Lock(), asyncio.Lock()
        self.active, self.resetting = True, False
        self.managed_prompt = ''
        self.managed_plugins = None
        self.generation = uuid.uuid4().hex
        self.history = self.runtime.store.kv_get("agent:history:" + identifier, [])
        self.pending = self.runtime.store.kv_get("agent:pending:" + identifier, [])

    @property
    def busy(self):
        return self.lock.locked() or any(not task.done() for task in self.tasks)

    def ensure_active(self):
        if not self.active:
            raise AgentInvalidatedError("Agent 声明已撤销或插件已卸载")

    def ensure_managed(self):
        self.ensure_active()
        if self.service.declarations.get(self.id, {}).get('persona_mode') != 'managed':
            raise ValueError('Agent 未声明自管理人格')

    def bind(self, owner):
        self.ensure_active()
        if owner not in self.handles:
            self.handles[owner] = AgentHandle(self, owner)
        return self.handles[owner]

    def clear_context(self):
        self.ensure_active()
        if self.id == "main":
            raise ValueError("仅非主 Agent 支持清空上下文")
        if self.busy or self.resetting:
            raise ValueError("Agent 运行中")
        self._clear_context()

    def _clear_context(self):
        self.history, self.pending = [], []
        self.save_history()
        self.save_pending()

    async def reset(self):
        self.ensure_active()
        if self.id == "main":
            raise ValueError("仅非主 Agent 支持重置")
        current = asyncio.current_task()
        if current in self.tasks or _CURRENT_AGENT.get() is self:
            raise ValueError("不能在当前 Agent 调用中等待重置自身")
        async with self.reset_lock:
            self.ensure_active()
            self.resetting = True
            try:
                jobs = list(self.tasks)
                for task in jobs:
                    task.cancel()
                await asyncio.gather(*jobs, return_exceptions=True)
                async with self.lock:
                    self.ensure_active()
                    self._clear_context()
                self.runtime.store.log("info", "agents", "agent.reset", data={"agent_id": self.id, "instance_id": self.generation})
                await self.dispatch("reset", {"instance_id": self.generation})
            finally:
                self.resetting = False

    def save_history(self):
        self.ensure_active()
        self.runtime.store.kv_set("agent:history:" + self.id, self.history)

    def save_pending(self):
        self.ensure_active()
        self.runtime.store.kv_set("agent:pending:" + self.id, [row for row in self.pending if not row.get("_temporary")])

    def take_pending(self, owner=None):
        self.ensure_active()
        taken = [row for row in self.pending if owner is None or row["owner"] == owner]
        self.pending = [] if owner is None else [row for row in self.pending if row["owner"] != owner]
        self.save_pending()
        return [{"role": row["role"], "content": row["content"], **({"_temporary": True} if row.get("_temporary") else {})} for row in taken]

    async def dispatch(self, event, payload):
        if not self.active:
            return
        for owner, callback in list(self.callbacks.get(event, [])):
            if not self.runtime.registry.loaded(owner):
                continue
            try:
                result = callback({"agent_id": self.id, **payload})
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                self.runtime.store.log("error", owner, "agent.callback.failed", run_id=payload.get("run_id", ""),
                    data={"agent_id": self.id, "event": event, "error": type(exc).__name__})

    def remove_owner(self, owner):
        if not self.active:
            return
        handle = self.handles.pop(owner, None)
        if handle:
            handle._valid = False
        self.tools = {name: tool for name, tool in self.tools.items() if tool.plugin_id != owner}
        self.callbacks = {event: [entry for entry in rows if entry[0] != owner] for event, rows in self.callbacks.items()}
        self.pending = [row for row in self.pending if row["owner"] != owner]
        self.save_pending()
        for task, source in list(self.tasks.items()):
            if source == owner:
                task.cancel()

    def dispose(self):
        self.active = False
        for task in list(self.tasks):
            task.cancel()
        self.tools.clear()
        self.callbacks.clear()

    async def run(self, goal, *, invocation=None, context="", instructions="", persist=True, timeout=300, run_id=None, target=None, metadata=None, temporary_context="", _injected=None):
        self.ensure_active()
        if self.id == "main":
            contexts = self.take_pending() if _injected is None else _injected
            if context:
                contexts.append({"role": "user", "content": str(context)})
            return await self.runtime.emit("wake", "agent-instance", goal or "处理注入的上下文", target=target,
                meta={**(metadata or {}), "injected_context": contexts}, temporary_context=temporary_context)
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 200000:
            raise ValueError("Agent 任务无效")
        async with self.lock:
            self.ensure_active()
            run_id = run_id or "agent:" + uuid.uuid4().hex
            target = target or (invocation.target if invocation else self.runtime.main_target())
            inv = Invocation(run_id, target, actor=invocation.actor if invocation else "",
                task_id=invocation.task_id if invocation else "", agent_id=self.id, instance=self)
            inv.metadata["data"] = copy.deepcopy(metadata or {})
            inv.metadata['wake_goal'] = goal
            profile = self.runtime.prepare_agent(inv)
            system = profile["prompt"] + "\nAgent：" + profile["name"] + "\n职责：" + profile["description"]
            if instructions:
                system += "\n本次任务：" + instructions
            injected = self.take_pending() if _injected is None else _injected
            inv.temporary_context = temporary_messages(temporary_context) + [
                {'role': row['role'], 'content': row['content']} for row in injected if row.get('_temporary')]
            injected = [row for row in injected if not row.get('_temporary')]
            messages = [{"role": "system", "content": system}, *(copy.deepcopy(self.history) if persist else []), *injected]
            if context:
                messages.append({"role": "user", "content": str(context)})
            messages.append({"role": "user", "content": goal})
            self.runtime.store.execute("INSERT INTO runs VALUES (?,NULL,?,NULL,'running',?,'')", (run_id, time.time(), encode({'agent_id': self.id, 'wake_goal': goal, 'agent_profile': {'name': profile['name']}})))
            job = asyncio.current_task()
            self.runtime.agent_jobs.setdefault(self.id, set()).add(job)
            try:
                await self.dispatch("started", {"run_id": run_id, "invocation": inv})
                await self.runtime.agent_slots.acquire()
                try:
                    async with asyncio.timeout(timeout) as deadline:
                        inv.control = AgentRunControl(self, inv, deadline)
                        token = _CURRENT_AGENT.set(self)
                        try:
                            result, usage = await self.runtime.agent_loop(messages, inv)
                        finally:
                            _CURRENT_AGENT.reset(token)
                finally:
                    if inv.control is None or inv.control.slot_held:
                        self.runtime.agent_slots.release()
                        if inv.control:
                            inv.control.slot_held = False
                outcome = {"run_id": run_id, "agent_id": self.id, "instance_id": self.generation,
                    "result": result, "usage": usage, "data": inv.metadata["data"]}
                self.runtime.store.execute("UPDATE runs SET status='done',finished=? WHERE id=?", (time.time(), run_id))
                if persist:
                    self.history = [row for row in messages if row.get("role") != "system"]
                    self.save_history()
                await self.dispatch("completed", {**outcome, "invocation": inv})
                return outcome
            except BaseException as exc:
                status = "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed"
                error = "Agent 已中断" if status == "interrupted" else str(exc)[:500] if isinstance(exc, (RuntimeError, ValueError)) else type(exc).__name__
                self.runtime.store.execute("UPDATE runs SET status=?,finished=?,error=? WHERE id=?", (status, time.time(), error, run_id))
                self.runtime.store.log("warning" if status == "interrupted" else "error", "agents", "agent." + status, run_id=run_id,
                    data={"agent_id": self.id, "error": error})
                await self.dispatch("cancelled" if status == "interrupted" else "failed", {"run_id": run_id, "error": error, "invocation": inv})
                raise
            finally:
                self.runtime.agent_jobs.get(self.id, set()).discard(job)
