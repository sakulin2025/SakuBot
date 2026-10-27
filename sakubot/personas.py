import re
import time
import uuid

from .components import visible_ids, migrate_saved


DEFAULT_PROMPT = "你是 SakuBot，主人的个人助手。自然、坦诚地与主人交流，持续记住共同经历。"
_UNSET = object()


def managed_persona(prompt, visible_plugins=None):
    """Validate plugin-owned runtime settings without storing a framework persona."""
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 100000:
        raise ValueError('自管理人格内容无效')
    if visible_plugins is not None and (not isinstance(visible_plugins, list) or not all(
            isinstance(item, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,40}', item) for item in visible_plugins)):
        raise ValueError('插件列表无效')
    return {'prompt': prompt, 'visible_plugins': visible_ids(sorted(set(visible_plugins))) if visible_plugins is not None else None}


class Personas:
    def __init__(self, store, config):
        self.store, self.config = store, config
        migrate_saved(store)
        if store.kv_get("personas") is None:
            now = time.time()
            store.kv_set("personas", {"default": {"id": "default", "name": "默认人格",
                "prompt": config.legacy_persona or DEFAULT_PROMPT, "created": now, "updated": now, "visible_plugins": None}})

    def list(self):
        return [{**row, "visible_plugins": row.get("visible_plugins")} for row in
            sorted(self.store.kv_get("personas", {}).values(), key=lambda row: row["created"])]

    def get(self, identifier):
        row = self.store.kv_get("personas", {}).get(identifier)
        if row is None:
            raise ValueError("人格不存在")
        return {**row, "visible_plugins": row.get("visible_plugins")}

    def save(self, name, prompt, identifier="", visible_plugins=_UNSET):
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("人格名称无效")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 100000:
            raise ValueError("人格内容无效")
        records = self.store.kv_get("personas", {})
        if identifier and identifier not in records:
            raise ValueError("人格不存在")
        if visible_plugins is _UNSET:
            visible_plugins = records.get(identifier, {}).get("visible_plugins")
        if visible_plugins is not None and (not isinstance(visible_plugins, list) or not all(
                isinstance(item, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,40}", item) for item in visible_plugins)):
            raise ValueError("插件列表无效")
        identifier = identifier or uuid.uuid4().hex[:12]
        now = time.time()
        records[identifier] = {"id": identifier, "name": name.strip(), "prompt": prompt,
            "created": records.get(identifier, {}).get("created", now), "updated": now,
            "visible_plugins": visible_ids(sorted(set(visible_plugins))) if visible_plugins is not None else None}
        self.store.kv_set("personas", records)
        self.store.log("info", "personas", "persona.saved", data={"persona_id": identifier})
        if getattr(self, "changed", None):
            self.changed()
        return dict(records[identifier])

    def delete(self, identifier):
        if identifier == self.config.settings.main_persona_id or (getattr(self, "in_use", None) and self.in_use(identifier)):
            raise ValueError("人格正在使用")
        records = self.store.kv_get("personas", {})
        if identifier not in records:
            raise ValueError("人格不存在")
        records.pop(identifier)
        self.store.kv_set("personas", records)
        self.store.log("info", "personas", "persona.deleted", data={"persona_id": identifier})
        if getattr(self, "changed", None):
            self.changed()

    def resolve(self, identifier=""):
        return self.get(identifier or self.config.settings.main_persona_id)
