"""QWeather native HTTP API with credential-scoped caching and no background polling."""
import asyncio
import copy
import math
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import aiohttp


class PluginError(ValueError):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def coordinates(value):
    try:
        lon, lat = (float(v.strip()) for v in str(value).split(","))
        if not math.isfinite(lon) or not math.isfinite(lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError
        return f"{lon:.2f}", f"{lat:.2f}"
    except (TypeError, ValueError):
        raise PluginError("坐标应为 经度,纬度，例如 116.41,39.92。") from None


def number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise PluginError(f"{name}应为 {minimum} 到 {maximum} 的整数。")
    return value


class QWeather:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.identity = None
        self.cache = {}
        self.failures = {}
        self.locks = {}
        self.locations = {}

    def connection(self):
        host = str(self.config.get("host", "")).strip().rstrip("/")
        key = str(self.config.get("key", "")).strip()
        if not host or not key:
            raise PluginError("请先在和风天气插件配置中填写 Host 和 Key。")
        if "://" not in host:
            host = "https://" + host
        try:
            parsed = urlsplit(host)
            port = parsed.port
        except ValueError:
            raise PluginError("API Host 格式无效。") from None
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment or port not in (None, 443)):
            raise PluginError("Host 请填写和风控制台分配的 HTTPS 根域名，不要包含接口路径或认证信息。")
        if "\r" in key or "\n" in key:
            raise PluginError("Key 格式无效，请重新从和风控制台复制。")
        connection = ("https://" + parsed.hostname.lower(), key)
        if self.identity != connection:
            self.cache.clear()
            self.failures.clear()
            self.locations.clear()
            self.identity = connection
        return connection

    async def close(self):
        if self.session is not None:
            await self.session.close()

    @staticmethod
    def api_error(code):
        messages = {
            "400": "请求参数无效，请检查地点和服务参数。",
            "401": "身份认证失败，请检查 API Key。",
            "402": "当前账号余额或可用请求额度不足。",
            "403": "当前凭据无权访问该服务，请检查项目权限和 Key 限制。",
            "404": "未找到该地点或服务没有对应数据。",
            "429": "已触及和风天气请求频率或配额限制，请稍后再试。",
        }
        return PluginError("和风天气：" + messages.get(str(code), f"服务请求失败（状态 {code}）。"))

    async def get(self, path, params, ttl, refresh=False):
        base, key = self.connection()
        identity = (base, key)
        cache_key = (identity, path, tuple(sorted((k, str(v)) for k, v in params.items())))
        async with self.locks.setdefault(cache_key, asyncio.Lock()):
            cached = self.cache.get(cache_key)
            if cached and not refresh and time.monotonic() - cached[0] < ttl:
                return {"data": copy.deepcopy(cached[1]), "fetched_at": cached[2], "cached": True,
                        "cache_age_seconds": round(time.monotonic() - cached[0]), "cache_ttl_seconds": ttl}
            failed = self.failures.get(cache_key)
            if failed and time.monotonic() < failed[0]:
                raise PluginError(failed[1])
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8), trust_env=False)
            cooldown = 60
            try:
                async with self.session.get(base + path, params=params,
                                            headers={"X-QW-Api-Key": key}, allow_redirects=False) as response:
                    if response.status != 200:
                        if response.status in (401, 402, 403, 429):
                            cooldown = 300
                        raise self.api_error(response.status)
                    data = await response.json()
                if not isinstance(data, dict):
                    raise PluginError("和风天气返回格式无效。")
                code = str(data.get("code", "200"))
                if code not in ("200", "204"):
                    if code in ("401", "402", "403", "429"):
                        cooldown = 300
                    raise self.api_error(code)
                if data.get("error"):
                    raise PluginError("和风天气返回服务错误，请检查地点及项目权限。")
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, PluginError) as exc:
                message = str(exc) if isinstance(exc, PluginError) else "和风天气连接失败、超时或响应无效，请检查 Host 和网络。"
                if len(self.failures) >= 256:
                    self.failures.pop(next(iter(self.failures)))
                self.failures[cache_key] = (time.monotonic() + cooldown, message)
                raise PluginError(message) from None
            fetched = stamp()
            if len(self.cache) >= 256:
                self.cache.pop(next(iter(self.cache)))
            self.cache[cache_key] = (time.monotonic(), data, fetched)
            self.failures.pop(cache_key, None)
            return {"data": copy.deepcopy(data), "fetched_at": fetched, "cached": False,
                    "cache_age_seconds": 0, "cache_ttl_seconds": ttl}

    async def geo(self, location="", adm="", country="", limit=10, refresh=False):
        location = str(location or self.config.get("default_city", "")).strip()
        if not location:
            raise PluginError("请指定城市，或先填写默认城市。")
        number(limit, "结果数量", 1, 20)
        if "," in location:
            lon, lat = coordinates(location)
            location = lon + "," + lat
        params = {"location": location, "number": limit, "lang": "zh"}
        if adm:
            params["adm"] = adm.strip()
        if country:
            params["range"] = country.strip()
        result = await self.get("/geo/v2/city/lookup", params, 7 * 86400, refresh)
        rows = result["data"].get("location", [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise PluginError("GeoAPI 返回的城市列表格式无效。")
        for row in rows:
            if row.get("id"):
                self.locations[str(row["id"])] = (time.monotonic() - result["cache_age_seconds"], dict(row))
        return {"query": location, "locations": rows, "refer": result["data"].get("refer", {}),
                "source": {"provider": "和风天气", "url": "https://www.qweather.com"},
                **{k: v for k, v in result.items() if k != "data"}}

    async def resolve(self, location="", adm=""):
        wanted = str(location or self.config.get("default_city", "")).strip()
        self.connection()
        cached = self.locations.get(wanted)
        if cached and not adm and time.monotonic() - cached[0] < 7 * 86400:
            chosen = cached[1]
            lon, lat = coordinates(f"{chosen.get('lon')},{chosen.get('lat')}")
            return {**chosen, "lon": lon, "lat": lat}
        found = await self.geo(wanted, adm)
        rows = found["locations"]
        if not rows:
            raise PluginError("GeoAPI 未找到城市，请换用城市名称、上级行政区或准确 Location ID。")
        if "," in wanted:
            lon, lat = coordinates(wanted)
            return {**rows[0], "lon": lon, "lat": lat, "coordinate_input": True}
        normalized = wanted.casefold().removesuffix("市")
        exact = [row for row in rows if wanted == str(row.get("id", ""))
                 or normalized == str(row.get("name", "")).casefold().removesuffix("市")]
        if len(exact) == 1:
            chosen = exact[0]
        elif len(rows) == 1:
            chosen = rows[0]
        else:
            return {"needs_selection": True, "query": wanted, "candidates": rows,
                    "note": "有多个候选城市，请结合上级行政区和对话明确的位置选择实际 Location ID，不猜用户所在地。"}
        lon, lat = coordinates(f"{chosen.get('lon')},{chosen.get('lat')}")
        return {**chosen, "lon": lon, "lat": lat}

    @staticmethod
    def attribution(data):
        return {"provider": "和风天气", "url": "https://www.qweather.com",
                "attributions": data.get("metadata", {}).get("attributions", []),
                "refer": data.get("refer", {})}

    async def service(self, service, place, days=3, hours=24, index_types="3,5", refresh=False):
        lat, lon = place["lat"], place["lon"]
        params = {"lang": "zh"}
        if service == "now":
            path, ttl = f"/weather/v1/current/{lat}/{lon}", 900
            params["localTime"] = "true"
        elif service == "daily":
            number(days, "预报天数", 1, 10)
            path, ttl = f"/weather/v1/daily/{lat}/{lon}", 3600
            params.update(days=days, localTime="true")
        elif service == "hourly":
            number(hours, "预报小时数", 1, 240)
            path, ttl = f"/weather/v1/hourly/{lat}/{lon}", 1800
            params.update(hours=hours, localTime="true")
        elif service == "warning":
            path, ttl = f"/weatheralert/v1/current/{lat}/{lon}", 300
            params["localTime"] = "true"
        elif service == "air":
            path, ttl = f"/airquality/v1/current/{lat}/{lon}", 1800
        elif service == "minutely":
            path, ttl = "/v7/minutely/5m", 300
            params["location"] = f"{lon},{lat}"
        elif service == "indices":
            if isinstance(index_types, str):
                index_types = ",".join(part.strip() for part in index_types.split(","))
            if not isinstance(index_types, str) or not re.fullmatch(r"\d+(,\d+)*", index_types.strip()):
                raise PluginError("指数类型请用逗号分隔的数字，例如 3,5（穿衣、紫外线）。")
            types = list(dict.fromkeys(int(v) for v in index_types.strip().split(",")))
            if any(v not in range(17) for v in types) or (0 in types and len(types) > 1):
                raise PluginError("指数类型支持0到16；0代表全部，不能与其他类型混用。")
            path, ttl = "/v7/indices/1d", 3600
            params.update(location=place["id"], type=",".join(str(v) for v in types))
        else:
            raise PluginError("服务支持 overview/now/daily/hourly/minutely/warning/air/indices。")
        result = await self.get(path, params, ttl, refresh)
        return {"service": service, "location": place, "source": self.attribution(result["data"]), **result}

    async def query(self, service="overview", location="", adm="", days=3, hours=24, index_types="3,5", refresh=False):
        if service not in ("overview", "now", "daily", "hourly", "minutely", "warning", "air", "indices"):
            raise PluginError("服务支持 overview/now/daily/hourly/minutely/warning/air/indices。")
        place = await self.resolve(location, adm)
        if place.get("needs_selection"):
            return place
        if service != "overview":
            return await self.service(service, place, days, hours, index_types, refresh)
        results = await asyncio.gather(self.service("now", place, refresh=refresh),
                                       self.service("daily", place, days=3, refresh=refresh), return_exceptions=True)
        response = {"location": place, "services": {}, "errors": {}, "source": {"provider": "和风天气", "url": "https://www.qweather.com"}}
        for kind, result in zip(("now", "daily"), results):
            if isinstance(result, PluginError):
                response["errors"][kind] = str(result)
            elif isinstance(result, BaseException):
                raise result
            else:
                response["services"][kind] = result
        return response
