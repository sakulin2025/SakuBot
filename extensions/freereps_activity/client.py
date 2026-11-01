from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import re
from urllib.parse import urlsplit
from uuid import UUID
import httpx

WORKOUT_KEYS = {'ID': 'id', 'UserID': 'user_id', 'Name': 'name', 'Source': 'source', 'Sources': 'sources',
    'RecordedBy': 'recorded_by', 'StartTime': 'start_time', 'EndTime': 'end_time', 'DurationSec': 'duration_sec',
    'Location': 'location', 'IsIndoor': 'is_indoor', 'ActiveEnergyBurned': 'active_energy_burned',
    'ActiveEnergyUnits': 'active_energy_units', 'TotalEnergy': 'total_energy', 'TotalEnergyUnits': 'total_energy_units',
    'Distance': 'distance', 'DistanceUnits': 'distance_units', 'AvgHeartRate': 'avg_heart_rate',
    'MaxHeartRate': 'max_heart_rate', 'MinHeartRate': 'min_heart_rate', 'ElevationUp': 'elevation_up', 'ElevationDown': 'elevation_down'}


LOCAL_ZONE = ZoneInfo('Asia/Shanghai')
# Only convert full ISO timestamps with an explicit offset. Dates and numeric
# measurements are deliberately left untouched.
_ISO_TIMESTAMP = re.compile(r'^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:?\d{2})$')


def local_times(value):
    if isinstance(value, dict):
        return {key: local_times(item) for key, item in value.items()}
    if isinstance(value, list):
        return [local_times(item) for item in value]
    if isinstance(value, str) and _ISO_TIMESTAMP.fullmatch(value):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00').replace('z', '+00:00')).astimezone(LOCAL_ZONE).isoformat()
        except ValueError:
            pass
    return value


def date_range(start='', end='', days=7):
    def parse(value, end_date=False):
        if not value:
            return None
        try:
            result = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if result.tzinfo is None:
                result = result.replace(tzinfo=LOCAL_ZONE)
            if len(value) == 10 and end_date:
                result += timedelta(days=1)
            return result.astimezone(timezone.utc)
        except (ValueError, TypeError):
            raise ValueError('日期格式应为 YYYY-MM-DD 或带时区的 ISO 时间') from None
    finish = parse(end, True) or datetime.now(timezone.utc)
    begin = parse(start) or finish - timedelta(days=days)
    if begin >= finish or (finish - begin).days > 3660:
        raise ValueError('时间范围无效或超过十年')
    return {'start': begin.isoformat(), 'end': finish.isoformat()}


def validate_url(url):
    try:
        u = urlsplit(url)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.query or u.fragment or any(c.isspace() for c in url):
            raise ValueError()
        _ = u.port
    except ValueError:
        raise ValueError('服务地址必须是完整 HTTP 或 HTTPS 地址') from None
    return url.rstrip('/')


def workout_id(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('训练 ID 格式无效') from None


class Client:
    def __init__(self, config):
        self.config = config
        self.http = httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False)

    async def close(self):
        await self.http.aclose()

    async def get(self, path, params=None):
        base = validate_url(self.config.get('base_url', ''))
        try:
            response = await self.http.get(base + '/api/v1/' + path, params={k: v for k, v in (params or {}).items() if v != '' and v is not None})
            if response.status_code != 200:
                raise ValueError('FreeReps 请求失败（HTTP ' + str(response.status_code) + '）')
            if len(response.content) > 12000000:
                raise ValueError('FreeReps 返回数据过大，请缩小时间范围')
            return local_times(response.json())
        except httpx.HTTPError:
            raise ValueError('无法连接 FreeReps') from None
        except (UnicodeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith(('FreeReps', '无法')):
                raise
            raise ValueError('FreeReps 返回的数据格式无效') from None

    async def workouts(self, start='', end='', workout_type='', days=7):
        params = date_range(start, end, days)
        if workout_type:
            params['type'] = workout_type
        result = await self.get('workouts', params)
        if result is None:
            return []
        if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
            raise ValueError('训练列表格式无效')
        return [{WORKOUT_KEYS.get(key, key): value for key, value in row.items()} for row in result]
