"""Validated incremental settings changes; running wakes keep their model snapshot."""
import asyncio

from pydantic import ValidationError
from ..config import Settings


class Configuration:
    def __init__(self, control):
        self.control, self.runtime = control, control.runtime

    async def apply(self, draft):
        if not isinstance(draft, dict):
            raise ValueError('配置须为对象')
        async with self.control.lock:
            return await self._apply(draft)

    async def _apply(self, draft):
        previous = self.runtime.config.settings
        providers=draft.get('providers', [])
        if not isinstance(providers,list) or any(not isinstance(row,dict) for row in providers):
            raise ValueError('供应商配置须为对象列表')
        for provider in providers:
            old = next((row for row in previous.providers if row.id == provider.get('id')), None)
            if old and not provider.get('api_key'):
                provider['api_key'] = old.api_key
        try:
            settings = Settings.model_validate(draft)
        except ValidationError:
            raise ValueError('配置字段、类型或引用无效') from None
        self.runtime.personas.get(settings.main_persona_id)
        before, after = set(previous.plugins), set(settings.plugins)
        enabled, disabled = [], []
        try:
            for name in before - after:
                await self.control.plugins.idle(name)
            self.runtime.config.save(settings)
            self.runtime.model.settings = settings
            for name in sorted(after - before):
                await self.runtime.registry.enable(name, start=self.runtime.sources_started)
                enabled.append(name)
            for name in sorted(before - after):
                await self.runtime.registry.disable(name)
                disabled.append(name)
        except BaseException as exc:
            self.runtime.config.save(previous)
            self.runtime.model.settings = previous
            for name in enabled:
                await self.runtime.registry.disable(name)
            for name in disabled:
                await self.runtime.registry.enable(name, start=self.runtime.sources_started)
            if isinstance(exc,(asyncio.CancelledError,ValueError,RuntimeError)):
                raise
            raise ValueError('插件配置未能应用（'+type(exc).__name__+'），已恢复原配置') from None
        self.runtime.agents.changed()
        if not self.runtime.current_run:
            await self.runtime.sync_main_worker()
        self.runtime.live.publish('conversation.settings', **settings.conversation.model_dump())
        self.runtime.store.log('info', 'control', 'config.applied', data={'fields': [key for key in Settings.model_fields if getattr(settings,key) != getattr(previous,key)]})
        return {'ok': True, 'config': self.runtime.config.public()}

    async def patch(self, values):
        if not isinstance(values, dict) or set(values) - set(Settings.model_fields):
            raise ValueError('配置字段无效')
        # A full snapshot is created at execution time, not when an operation is queued.
        async with self.control.lock:
            return await self._apply({**self.runtime.config.settings.model_dump(), **values})

    async def maintain(self):
        runtime = self.runtime
        if not any(runtime.agent_jobs.values()):
            configured = runtime.config.settings.agent_concurrency
            if configured != self.control.agent_concurrency:
                runtime.agent_slots = asyncio.Semaphore(configured)
                self.control.agent_concurrency = configured
        if not runtime.current_run and not runtime.config.settings.ready() and runtime.main_job:
            await runtime.sync_main_worker()
