"""Read-only client for ScanElf's native Bearer HTTP API."""

import asyncio
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit, urlunsplit

import aiohttp


class PluginError(ValueError):
    pass


def normalize_mac(value):
    compact = re.sub(r"[:-]", "", str(value).strip())
    if not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        return None
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2)).upper()


class ScanElf:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.lock = asyncio.Lock()
        self.cache = {}
        self.credentials = None

    def base_url(self):
        value = str(self.config.get("base_url", "")).strip().rstrip("/")
        try:
            parts = urlsplit(value)
            port = parts.port
        except ValueError:
            raise PluginError("ScanElf URL 格式无效。") from None
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username or parts.password or parts.query or parts.fragment):
            raise PluginError("请在插件页填写 ScanElf 的 HTTP/HTTPS 地址，token 填在独立配置项。")
        path = parts.path.removesuffix("/api/v1").rstrip("/")
        host = parts.hostname.lower()
        if ":" in host:
            host = "[" + host + "]"
        if port is not None and (parts.scheme, port) not in (("http", 80), ("https", 443)):
            host += f":{port}"
        return urlunsplit((parts.scheme, host, path, "", ""))

    def connection(self):
        base = self.base_url()
        token = str(self.config.get("token", "")).strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token:
            raise PluginError("请先在 ScanElf 插件配置页填写 API token。")
        return base, token

    async def close(self):
        if self.session is not None:
            await self.session.close()

    async def _get(self, connection, path, params=None):
        base, token = connection
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10), trust_env=False,
            )
        try:
            async with self.session.get(
                base + "/api/v1/" + path, params=params,
                headers={"Authorization": "Bearer " + token}, allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise PluginError("ScanElf 认证失败，请检查 API token 是否正确或已被撤销。")
                if response.status != 200:
                    raise PluginError(f"ScanElf 请求失败（HTTP {response.status}）。")
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise PluginError("ScanElf 连接失败、超时或响应格式错误，请检查 URL、网络和服务状态。") from None
        if not isinstance(data, dict):
            raise PluginError("ScanElf 返回的数据格式无效。")
        return data

    @staticmethod
    def _rows(data, field):
        rows = data.get(field)
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not normalize_mac(row.get("mac", "")) for row in rows
        ):
            raise PluginError("ScanElf 返回的设备列表格式无效。")
        return [row for row in rows if not row.get("ignored", False)]

    async def _cached(self, kind, refresh=False):
        connection = self.connection()
        async with self.lock:
            if self.credentials != connection:
                self.cache.clear()
                self.credentials = connection
            cached = self.cache.get(kind)
            if not refresh and cached and time.monotonic() - cached[0] < 30:
                return cached[1]
            if kind == "status":
                data = await self._get(connection, "status")
                self._rows(data, "devices")
            else:
                rows = {}
                offset = 0
                while True:
                    page = await self._get(connection, "devices", {"limit": 100, "offset": offset})
                    items = self._rows(page, "items")
                    for row in items:
                        rows[normalize_mac(row["mac"])] = row
                    count = len(page["items"])
                    offset += count
                    total = page.get("total")
                    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                        raise PluginError("ScanElf 返回的设备总数格式无效。")
                    if not count or offset >= total:
                        break
                data = list(rows.values())
            self.cache[kind] = (time.monotonic(), data)
            return data

    async def status(self, refresh=False):
        return await self._cached("status", refresh)

    async def devices(self, refresh=False):
        return await self._cached("devices", refresh)

    async def activity(self, mac, limit=100, before=0):
        mac = normalize_mac(mac)
        if not mac:
            raise PluginError("请指定有效的设备 MAC。")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise PluginError("limit 必须是1到100的整数。")
        if isinstance(before, bool) or not isinstance(before, int) or before < 0:
            raise PluginError("before 必须是非负整数；0从最新记录开始。")
        params = {"limit": limit}
        if before:
            params["before"] = before
        data = await self._get(self.connection(), "devices/" + quote(mac, safe="") + "/activity", params)
        items, cursor = data.get("items"), data.get("next_cursor")
        if "next_cursor" not in data or not isinstance(items, list) or any(
            not isinstance(item, dict) or normalize_mac(item.get("mac")) != mac
            or isinstance(item.get("id"), bool) or not isinstance(item.get("id"), int) or item["id"] < 1
            or not isinstance(item.get("event"), str) or not isinstance(item.get("at"), str)
            for item in items
        ):
            raise PluginError("ScanElf 返回的设备时间线格式无效。")
        if cursor is not None and (isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 1
                                   or not items or cursor != items[-1]["id"] or (before and cursor >= before)):
            raise PluginError("ScanElf 返回的时间线分页游标无效。")
        return {"items": items, "next_cursor": cursor}

    @staticmethod
    def status_info(data):
        fresh = False
        try:
            at = datetime.fromisoformat(data["last_snapshot_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - at).total_seconds()
            fresh = -5 <= age <= 60
        except (KeyError, TypeError, AttributeError, ValueError):
            pass
        reliable = data.get("scanner_connected") is True and fresh
        return {
            "scanner_connected": data.get("scanner_connected") is True,
            "last_snapshot_at": data.get("last_snapshot_at"),
            "snapshot_fresh": fresh,
            "data_reliable": reliable,
            "online_count": data.get("online_count"),
            "note": ("在线状态沿用 ScanElf 的延迟下线规则。" if reliable else
                     "扫描器断连或快照过期，设备列表仅为最后已知状态，不能判断设备当前是否在线。"),
        }
