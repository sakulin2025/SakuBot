"""Read-only native Minecraft status probes. No RCON or external status service."""
import asyncio
import ipaddress
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from mcstatus import BedrockServer, JavaServer


class PluginError(ValueError):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def address(value):
    if not isinstance(value, str):
        raise PluginError("服务器地址必须是文本。")
    value = value.strip()
    if not value or len(value) > 320 or any(c.isspace() for c in value) or any(c in value for c in '/?#@\\\x00'):
        raise PluginError("请填写 IP 或域名，可带 :端口，不要填写网址或路径。")
    # Bare IPv6 is a host, not a host:port pair.
    try:
        ip = ipaddress.ip_address(value)
        return f"[{ip.compressed}]" if ip.version == 6 else str(ip)
    except ValueError:
        pass
    try:
        parts = urlsplit("//" + value)
        host, port = parts.hostname, parts.port
        if not host or parts.username or parts.password or parts.path or value.endswith(":"):
            raise ValueError
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
        if ":" in host:
            host = "[" + ipaddress.IPv6Address(host).compressed + "]"
        else:
            host = host.encode("idna").decode("ascii").lower()
            if any(not (c.isalnum() or c in '.-_') for c in host):
                raise ValueError
        return host + (f":{port}" if port is not None else "")
    except (ValueError, UnicodeError):
        raise PluginError("地址或端口无效；IPv6 带端口时请写成 [IPv6]:端口。") from None


class StatusClient:
    def __init__(self):
        self.cache = {}
        self.locks = {}
        self.parallel = asyncio.Semaphore(6)

    @staticmethod
    def key(record):
        return record["edition"], record["address"]

    def peek(self, record):
        cached = self.cache.get(self.key(record))
        if not cached:
            return None
        return {**cached[1], "cached": True, "age_seconds": round(time.monotonic() - cached[0], 1)}

    def forget(self, record):
        self.cache.pop(self.key(record), None)

    async def query(self, record, refresh=False):
        key = self.key(record)
        async with self.locks.setdefault(key, asyncio.Lock()):
            cached = self.peek(record)
            if cached and cached["age_seconds"] < 30 and not refresh:
                return cached
            async with self.parallel:
                try:
                    async with asyncio.timeout(10):
                        if record["edition"] == "java":
                            server = await JavaServer.async_lookup(record["address"], timeout=4)
                        else:
                            server = BedrockServer.lookup(record["address"], timeout=4)
                        result = await server.async_status(tries=1)
                        data = {
                            "online": True, "state": "online", "checked_at": stamp(),
                            "version": str(result.version.name)[:300], "protocol": result.version.protocol,
                            "motd": result.motd.to_plain()[:4000], "latency_ms": round(result.latency, 1),
                            "players_online": result.players.online, "players_max": result.players.max,
                            "player_sample": [str(player.name)[:100] for player in
                                              (getattr(result.players, "sample", None) or [])[:30]],
                            "sample_note": "玩家样本由服务器自报，可能隐藏、不完整或为自定义文字。",
                        }
                        if record["edition"] == "bedrock":
                            data.update(map_name=result.map_name, gamemode=result.gamemode)
                except Exception as exc:
                    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
                        reason = "查询超时。"
                    elif isinstance(exc, socket.gaierror):
                        reason = "域名解析失败。"
                    elif isinstance(exc, ConnectionRefusedError):
                        reason = "连接被拒绝，请检查地址、端口与服务状态。"
                    else:
                        reason = "未收到有效的 Minecraft 状态响应，请检查版本类型、网络及服务器状态查询设置。"
                    data = {"online": None, "state": "unreachable", "checked_at": stamp(),
                            "error": reason, "error_type": type(exc).__name__,
                            "note": "不可达不等于服务器已经关闭，也可能是网络、DNS 或状态查询未开放。"}
                self.cache[key] = (time.monotonic(), data)
                return {**data, "cached": False, "age_seconds": 0}
