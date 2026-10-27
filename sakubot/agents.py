"""Live plugin agent declarations with persistent user overrides."""
import copy
import re
import uuid


class Agents:
    def __init__(self, runtime):
        self.runtime = runtime
        self.declarations = {}
        self.instances = {}
        self.revision = uuid.uuid4().hex

    def get(self, identifier, owner=None):
        if identifier != "main" and identifier not in self.declarations:
            self.raw(identifier)
        if identifier not in self.instances:
            from .agent_instance import AgentInstance
            self.instances[identifier] = AgentInstance(self, identifier)
        instance = self.instances[identifier]
        return instance.bind(owner or self.raw(identifier)["plugin_id"]) if owner else instance

    def reset(self):
        for instance in self.instances.values():
            instance.dispose()
        self.instances.clear()
        self.declarations.clear()
        self.changed()

    def changed(self):
        self.revision = uuid.uuid4().hex

    def definition(self, plugin, record):
        identifier = record.get("id", "")
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", identifier):
            raise ValueError("Agent ID 无效")
        name, description = record.get("name"), record.get("description", "")
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("Agent 名称无效")
        if not isinstance(description, str) or len(description) > 10000:
            raise ValueError("Agent 描述无效")
        persona_id, model_id = record.get("persona_id", ""), record.get("model_id", "")
        if not isinstance(persona_id, str) or not isinstance(model_id, str):
            raise ValueError("Agent 默认配置无效")
        persona_mode = record.get('persona_mode') or ('library' if persona_id else 'default')
        if persona_mode not in ('default', 'library', 'managed'):
            raise ValueError('人格模式无效')
        if record.get('persona') is not None:
            raise ValueError('自管理人格需通过 Agent 实例设置')
        if persona_mode == 'library' and not persona_id:
            raise ValueError('请选择人格')
        if persona_mode != 'library':
            persona_id = ''
        return {"id": plugin + ":" + identifier, "local_id": identifier, "plugin_id": plugin,
            "name": name.strip(), "description": description, "persona_id": persona_id, "model_id": model_id,
            "persona_mode": persona_mode}

    def replace(self, plugin, records):
        # Validate the complete replacement before publishing any declaration.
        if not isinstance(records, list) or len(records) > 500:
            raise ValueError("Agent 声明列表无效")
        definitions = [self.definition(plugin, record) for record in records]
        if len({row["id"] for row in definitions}) != len(definitions):
            raise ValueError("Agent ID 重复")
        removed = {key for key, row in self.declarations.items() if row["plugin_id"] == plugin} - {row["id"] for row in definitions}
        self.cancel(removed)
        self.declarations = {key: row for key, row in self.declarations.items() if row["plugin_id"] != plugin}
        self.declarations.update({row["id"]: row for row in definitions})
        self.changed()
        self.runtime.store.log("info", plugin, "agents.updated", data={"agent_ids": [row["id"] for row in definitions]})

    def declare(self, plugin, identifier, name, description="", *, persona_id="", model_id="", persona_mode=""):
        row = self.definition(plugin, {"id": identifier, "name": name, "description": description,
            "persona_id": persona_id, "model_id": model_id, "persona_mode": persona_mode})
        self.declarations[row["id"]] = row
        self.changed()
        self.runtime.store.log("info", plugin, "agent.declared", data={"agent_id": row["id"]})
        return row["id"]

    def cancel(self, identifiers):
        for identifier in identifiers:
            instance = self.instances.pop(identifier, None)
            if instance:
                instance.dispose()
            for task in list(self.runtime.agent_jobs.get(identifier, set())):
                task.cancel()

    def remove(self, plugin, identifier=None):
        if identifier is None:
            for instance in self.instances.values():
                instance.remove_owner(plugin)
        self.cancel({key for key, row in self.declarations.items()
            if row["plugin_id"] == plugin and (identifier is None or row["local_id"] == identifier)})
        self.declarations = {key: row for key, row in self.declarations.items()
            if not (row["plugin_id"] == plugin and (identifier is None or row["local_id"] == identifier))}
        self.changed()

    def raw(self, identifier):
        if identifier == "main":
            return {"id": "main", "local_id": "main", "plugin_id": "", "name": "主 Agent",
                "description": "", "persona_id": "", "model_id": "", "persona_mode": "default"}
        row = self.declarations.get(identifier)
        if row is None or not self.runtime.registry.loaded(row["plugin_id"]):
            raise ValueError("Agent 未声明或所属插件未启用")
        return row

    def profile(self, identifier):
        row = self.raw(identifier)
        settings = self.runtime.config.settings
        override = settings.agent_settings.get(identifier)
        chosen_persona = override.persona_id if override else ""
        chosen_model = override.model_id if override else ""
        managed = row.get('persona_mode') == 'managed'
        if managed:
            chosen_persona = ''
        persona_id = ('managed:' + identifier) if managed else chosen_persona or row["persona_id"] or settings.main_persona_id
        model_id = chosen_model or row["model_id"] or settings.main_model_id
        _, model = settings.selected_model(model_id=model_id)
        personas = {item["id"]: item for item in self.runtime.personas.list()}
        instance = self.instances.get(identifier)
        persona = {'name': '自管理'} if managed else personas.get(persona_id)
        return {**row, "persona_id": chosen_persona, "model_id": chosen_model,
            "plugin_persona_id": row["persona_id"], "plugin_model_id": row["model_id"],
            "effective_persona_id": persona_id, "effective_model_id": model_id,
            "persona_source": "override" if chosen_persona else "managed" if managed else "plugin" if row["persona_id"] else "default",
            "model_source": "override" if chosen_model else "plugin" if row["model_id"] else "default",
            "persona_name": persona["name"] if persona else "人格不可用",
            "model_name": (model.name or model.model_id) if model else "模型不可用",
            "busy": self.instances[identifier].busy if identifier in self.instances else False,
            "resetting": self.instances[identifier].resetting if identifier in self.instances else False,
            "ready": bool(model and persona and (not managed or (instance and instance.managed_prompt))), "enabled": settings.enabled if identifier == "main" else True}

    def list(self):
        return [self.profile("main"), *(self.profile(key) for key, row in self.declarations.items()
            if self.runtime.registry.loaded(row["plugin_id"]))]

    def visible_plugins(self, identifier):
        row = self.profile(identifier)
        if row['persona_mode'] == 'managed':
            instance = self.instances.get(identifier)
            return copy.deepcopy(instance.managed_plugins) if instance else []
        return copy.deepcopy(self.runtime.personas.get(row['effective_persona_id']).get('visible_plugins'))

    def snapshot(self, identifier):
        row = copy.deepcopy(self.profile(identifier))
        if not row['ready']:
            raise ValueError('Agent 的人格或模型不可用，自管理人格由插件设置')
        row['prompt'] = self.instances[identifier].managed_prompt if row['persona_mode'] == 'managed' else self.runtime.personas.get(row['effective_persona_id'])['prompt']
        row['_visible_plugins'] = self.visible_plugins(identifier)
        return row

    def persona_in_use(self, identifier):
        settings = self.runtime.config.settings
        return (any(value.persona_id == identifier and self.declarations.get(key, {}).get("persona_mode") != "managed"
                 for key, value in settings.agent_settings.items())
            or any(row["persona_id"] == identifier for row in self.declarations.values()))
