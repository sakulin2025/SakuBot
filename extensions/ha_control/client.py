"""Home Assistant client, initialization and entity permission enforcement."""
import copy
import datetime as dt
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests


class PluginError(ValueError):
    pass


POLICIES = {"controllable", "readonly", "ignore"}
CONTROL = {"light", "switch", "input_boolean", "fan", "climate", "cover", "media_player",
           "select", "input_select", "input_number", "number"}
READONLY = {"sensor", "binary_sensor", "weather", "person", "device_tracker"}
DIAGNOSTIC = ("indicator", "diagnostic", "_led", "指示灯", "状态灯")


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def suggested(eid, name):
    if any(hint in f"{eid} {name}".lower() for hint in DIAGNOSTIC):
        return "ignore"
    domain = eid.split(".")[0]
    return "controllable" if domain in CONTROL else "readonly" if domain in READONLY else "ignore"


class HomeAssistant:
    def __init__(self, config, data_dir, save):
        self.config = config
        self.data_dir = Path(data_dir)
        self.save = save

    @property
    def base(self):
        value = str(self.config.get("base_url") or "").rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise PluginError("请在插件页面填写有效的 Home Assistant URL 和 token")
        return value

    def api(self, method, path, payload=None, text=False):
        token = str(self.config.get("token") or "").strip()
        if not token:
            raise PluginError("请先在插件页面填写 Home Assistant token")
        try:
            response = requests.request(method, self.base + path, json=payload,
                                        headers={"Authorization": f"Bearer {token}"},
                                        timeout=max(1, min(int(self.config.get("timeout", 30)), 300)),
                                        allow_redirects=False)
            if response.status_code == 401:
                raise PluginError("Home Assistant token 无效或已过期")
            if response.status_code not in (200, 201):
                raise PluginError(f"Home Assistant 请求失败（HTTP {response.status_code}）")
            return response.text if text else response.json()
        except (requests.RequestException, ValueError) as exc:
            if isinstance(exc, PluginError):
                raise
            raise PluginError("Home Assistant 连接失败或响应格式错误") from None

    def draft(self):
        try:
            draft = json.loads((self.data_dir / "draft.json").read_text())
        except (OSError, ValueError):
            raise PluginError("尚无初始化草稿，请先 scan 扫描") from None
        if draft.get("source_url") != self.base:
            raise PluginError("HA 地址已更改，请重新扫描初始化")
        return draft

    def save_draft(self, draft):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp = self.data_dir / "draft.json.tmp"
        temp.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.data_dir / "draft.json")
        self.config["initialization_status"] = (
            f"草稿：{len(draft['rooms'])} 个区域，{len(draft['entities'])} 个实体；"
            "请由管理员逐个房间确认并 build。现有生效配置保持生效。"
        )
        self.save()

    def scan(self):
        states = self.api("GET", "/api/states")
        template = "{% for s in states %}{{ s.entity_id }}|{{ area_name(s.entity_id) or '' }}\n{% endfor %}"
        text = self.api("POST", "/api/template", {"template": template}, text=True)
        areas = dict(line.split("|", 1) for line in text.splitlines() if "|" in line)
        entities = []
        rooms = {}
        for state in states:
            eid = state.get("entity_id", "")
            if not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", eid):
                continue
            name = (state.get("attributes") or {}).get("friendly_name") or eid
            area = areas.get(eid, "").strip() or "__unassigned__"
            rooms.setdefault(area, {"__template_key": "room", "area": area,
                                   "name": "未分配区域" if area == "__unassigned__" else area,
                                   "enabled": False, "reviewed": False})
            entities.append({"__template_key": "entity", "entity_id": eid, "name": name,
                             "area": area, "policy": suggested(eid, name), "alias": "", "group": "", "reviewed": False})
        draft = {"source_url": self.base, "scanned_at": stamp(), "rooms": list(rooms.values()), "entities": entities}
        self.save_draft(draft)
        return {"message": "扫描完成。所有房间默认停用，实体策略只是建议。先让管理员选择房间，再逐个确认实体。",
                "rooms": self.rooms(draft), "entity_count": len(entities)}

    @staticmethod
    def rooms(draft):
        return [{**room, "entity_count": sum(e["area"] == room["area"] for e in draft["entities"])}
                for room in draft["rooms"]]

    def initialize(self, action, area="", enabled=False, entity_id="", policy="", alias=None, group=None, confirmed=False):
        if action == "status":
            return {"initialized": self.config.get("initialized", False),
                    "has_draft": (self.data_dir / "draft.json").is_file(),
                    "status": self.config.get("initialization_status", "尚未初始化"),
                    "built_at": self.config.get("built_at", ""), "rooms": self.config.get("rooms", []),
                    "entities": self.config.get("entities", [])}
        if action == "scan":
            # Scanning replaces a draft, never the effective config.
            if (self.data_dir / "draft.json").exists() and not confirmed:
                raise PluginError("已有草稿；重新扫描会覆盖草稿，管理员确认后再传 confirmed=true")
            return self.scan()
        if action == "reset":
            if not confirmed:
                raise PluginError("reset 会清除初始化配置，需管理员明确确认；用户要求记忆和操作手册保留")
            for key, value in {"initialized": False, "rooms": [], "entities": [],
                               "source_url": "", "built_at": "", "initialization_status": "尚未初始化"}.items():
                self.config[key] = value
            (self.data_dir / "draft.json").unlink(missing_ok=True)
            self.save()
            return {"message": "已重置，需重新初始化后才能查询和控制"}
        draft = self.draft()
        if action == "rooms":
            return self.rooms(draft)
        if action == "entities":
            return [e for e in draft["entities"] if not area or e["area"] == area]
        if action == "room":
            room = next((r for r in draft["rooms"] if r["area"] == area), None)
            if room is None:
                raise PluginError("草稿中不存在该房间")
            room.update(enabled=enabled, reviewed=True)
        elif action == "policy":
            entity = next((e for e in draft["entities"] if e["entity_id"] == entity_id), None)
            if entity is None or policy not in POLICIES:
                raise PluginError("实体不存在或策略不是 controllable/readonly/ignore")
            entity.update(policy=policy, reviewed=True)
            if alias is not None:
                entity["alias"] = alias
            if group is not None:
                entity["group"] = group
        elif action == "review_room":
            if not confirmed:
                raise PluginError("先向管理员展示本房间所有实体建议，得到确认后再批量采纳")
            if not any(r["area"] == area for r in draft["rooms"]):
                raise PluginError("草稿中不存在该房间")
            for entity in draft["entities"]:
                if entity["area"] == area:
                    entity["reviewed"] = True
        elif action == "build":
            if not confirmed:
                raise PluginError("先向管理员复述区域与实体策略，确认后 confirmed=true 发布")
            enabled_areas = {r["area"] for r in draft["rooms"] if r["enabled"] and r["reviewed"]}
            if any(not e["reviewed"] for e in draft["entities"] if e["area"] in enabled_areas):
                raise PluginError("启用的房间中仍有未经管理员确认的实体，请逐项 policy 或确认 review_room")
            self.config.update(initialized=True, source_url=self.base, built_at=stamp(),
                               rooms=copy.deepcopy(draft["rooms"]), entities=copy.deepcopy(draft["entities"]))
            self.config["initialization_status"] = f"已完成：启用 {len(enabled_areas)} 个房间，允许 {sum(e['policy'] != 'ignore' and e['area'] in enabled_areas for e in draft['entities'])} 个实体。下方房间和实体列表为生效配置。"
            self.save()
            return self.initialize("status")
        else:
            raise PluginError("未知初始化操作")
        self.save_draft(draft)
        return {"message": "已更新草稿；完成后调用 build 发布到插件配置页面", "rooms": self.rooms(draft)}

    def allowed_entities(self):
        if self.config.get("initialized") is not True:
            raise PluginError("尚未完成初始化。请管理员配置连接后，让 AI 开始 HA 初始化")
        if self.config.get("source_url") != self.base:
            raise PluginError("HA 地址已更改，请由管理员重新初始化")
        areas = {r["area"] for r in self.config.get("rooms", []) if r.get("enabled") is True}
        entities = {}
        for entity in self.config.get("entities", []):
            eid = entity.get("entity_id", "")
            if eid in entities:
                raise PluginError("实体配置重复，请管理员在插件页面修正")
            if entity.get("area") in areas and entity.get("policy") in ("readonly", "controllable"):
                entities[eid] = entity
        return entities

    def entity(self, entity_id, control=False):
        if not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity_id):
            raise PluginError("请使用有效的完整实体 ID")
        item = self.allowed_entities().get(entity_id)
        if item is None or (control and item.get("policy") != "controllable"):
            raise PluginError("实体未授权、所在房间已停用，或实体策略不允许本次操作")
        return item

    def entity_metadata(self, item, attributes=None):
        attributes = attributes or {}
        eid = item["entity_id"]
        name = item.get("name") or attributes.get("friendly_name") or eid
        aliases = [value.strip() for value in str(item.get("alias") or "").split("/") if value.strip()]
        return {
            "entity_id": eid, "name": name,
            "friendly_name": attributes.get("friendly_name") or name,
            "display_name": aliases[0] if aliases else name,
            "domain": eid.split(".")[0],
            "area": item.get("area", ""), "alias": item.get("alias", ""),
            "group": item.get("group", ""), "policy": item.get("policy"),
        }

    def catalog(self):
        items = [self.entity_metadata(item) for item in self.allowed_entities().values()]
        return {"entities": items[:100], "total": len(items), "truncated": len(items) > 100}

    @staticmethod
    def lighting_switch(item):
        if item["domain"] not in ("switch", "input_boolean"):
            return False
        names = " ".join(str(item.get(key) or "") for key in
                         ("name", "friendly_name", "alias", "group")).casefold()
        return (not any(hint in names for hint in DIAGNOSTIC)
                and any(hint in names for hint in ("灯", "light", "lamp")))

    def query(self, entity_id="", match="", domain="", summary=False):
        allowed = self.allowed_entities()
        if entity_id:
            self.entity(entity_id)
            states = [self.api("GET", "/api/states/" + entity_id)]
        else:
            states = self.api("GET", "/api/states")
        result = []
        related = []
        domains = {value.strip() for value in domain.split(",") if value.strip()}
        needle = match.strip().casefold()
        for state in states:
            eid = state.get("entity_id")
            if eid not in allowed:
                continue
            attrs = state.get("attributes") or {}
            item = self.entity_metadata(allowed[eid], attrs)
            if needle and needle not in " ".join(str(item.get(key) or "") for key in
                                                ("entity_id", "name", "friendly_name", "area", "alias", "group")).casefold():
                continue
            value = state.get("state")
            item.update(state=value, state_text={
                "on": "开启", "off": "关闭", "unknown": "未知", "unavailable": "不可用",
            }.get(value, value))
            if not summary:
                item["attributes"] = {key: attrs[key] for key in (
                    "friendly_name", "device_class", "unit_of_measurement", "brightness", "current_temperature",
                    "temperature", "hvac_mode", "percentage", "current_position", "volume_level", "options",
                    "min", "max", "step",
                ) if key in attrs}
            if domains and item["domain"] not in domains:
                if "light" in domains and self.lighting_switch(item):
                    related.append(item)
                continue
            result.append(item)
        response = {"entities": result[:100], "total": len(result), "truncated": len(result) > 100}
        if summary:
            counts = {}
            for item in result:
                key = item["domain"]
                counts[key] = counts.get(key, 0) + 1
            response["domains"] = counts
        if related:
            response.update(
                related_entities=related[:100], related_total=len(related), related_truncated=len(related) > 100,
                note="名称、别名或分组表明 related_entities 可能用于照明，但其 HA 技术类型是 switch/input_boolean。"
                     "查询灯的状态时请同时参考这些实体，不能因为 light 类型为空就说没有灯。控制时仍使用实际 entity_id。",
            )
        elif domains and not result:
            response["note"] = "未匹配到指定 HA 技术类型，不代表不存在这个用途的设备。请清空 domain，按名称、别名或分组查询。"
        return response

    def plan(self, entity_id, action, params, force=False):
        item = self.entity(entity_id, control=True)
        if any(h in f"{entity_id} {item.get('name', '')}".lower() for h in DIAGNOSTIC) and not force:
            raise PluginError("这是指示灯/诊断类实体，需要管理员明确指定 force=true")
        domain = entity_id.split(".")[0]
        data = {"entity_id": entity_id}
        params = {k: v for k, v in params.items() if v is not None}
        if action in ("on", "off"):
            if params:
                raise PluginError("on/off 不接受额外参数，请使用 set")
            if domain not in {"light", "switch", "input_boolean", "fan", "climate", "media_player", "cover"}:
                raise PluginError("该实体不支持开关操作")
            service = ("open_cover" if action == "on" else "close_cover") if domain == "cover" else ("turn_on" if action == "on" else "turn_off")
        elif action == "set":
            mapping = {
                "light": {"brightness": ("turn_on", "brightness_pct"), "mode": ("turn_on", "effect")},
                "climate": {"temperature": ("set_temperature", "temperature"), "mode": ("set_hvac_mode", "hvac_mode")},
                "fan": {"brightness": ("set_percentage", "percentage")},
                "cover": {"position": ("set_cover_position", "position")},
                "media_player": {"brightness": ("volume_set", "volume_level")},
                "select": {"option": ("select_option", "option")},
                "input_select": {"option": ("select_option", "option")},
                "number": {"value": ("set_value", "value")},
                "input_number": {"value": ("set_value", "value")},
            }.get(domain, {})
            if not params or any(k not in mapping for k in params):
                raise PluginError("参数不适用于此实体")
            services = {mapping[k][0] for k in params}
            if len(services) != 1:
                raise PluginError("这些参数使用不同服务，请分别调用 set")
            service = services.pop()
            for key, value in params.items():
                if key in ("brightness", "temperature", "position", "value"):
                    value = float(value)
                    if not math.isfinite(value):
                        raise PluginError("数值参数必须是有限数")
                if key in ("brightness", "position") and not 0 <= float(value) <= 100:
                    raise PluginError("亮度、百分比、音量和位置必须在0至100之间")
                if domain == "climate" and key == "mode" and value not in {"off", "heat", "cool", "auto", "dry", "fan_only", "heat_cool"}:
                    raise PluginError("不支持的空调模式")
                data[mapping[key][1]] = float(value) / 100 if domain == "media_player" else value
        else:
            raise PluginError("action 只能是 on/off/set")
        return {"domain": domain, "service": service, "data": data}

    def execute(self, plan):
        self.api("POST", f"/api/services/{plan['domain']}/{plan['service']}", plan["data"])
        return {"success": True, **plan}

    def manual(self):
        return str(self.config.get("operation_manual") or "")

    def update_manual(self, action, content=""):
        if action == "read":
            return {"title": "用户要求记忆和操作手册", "content": self.manual(), "shared_across_sessions": True}
        if action not in ("append", "write", "clear"):
            raise PluginError("action 只能是 read/append/write/clear")
        if not isinstance(content, str):
            raise PluginError("手册内容必须是文本")
        if action == "append":
            if not content.strip():
                raise PluginError("请提供要记住的要求")
            text = "\n\n".join(filter(None, (self.manual().rstrip(), content.strip())))
        else:
            text = content if action == "write" else ""
        self.config["operation_manual"] = text
        self.save()
        return {"saved": True, "title": "用户要求记忆和操作手册", "content": text,
                "shared_across_sessions": True, "device_operations": 0}
