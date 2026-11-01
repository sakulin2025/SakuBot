"""Render a workout report locally from FreeReps samples, without map services."""
import io
import math
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W = 1000
RENDER_SCALE = 3
OUTPUT_SCALE = 1.5
BG = '#0b1015'
INK = '#e8f1ef'
MUTED = '#839b98'
GREEN = '#71dfb1'
FONT_PATHS = ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/System/Library/Fonts/PingFang.ttc')
BOLD_FONT_PATHS = ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/System/Library/Fonts/PingFang.ttc')
WORKOUT_NAMES = {
    'running': '跑步', 'run': '跑步', 'walking': '步行', 'walk': '步行',
    'cycling': '单车', 'biking': '单车', 'bicycle': '单车', 'swimming': '游泳',
    'outdoor running': '户外跑步', 'indoor running': '室内跑步',
    'outdoor walking': '户外步行', 'indoor walking': '室内步行',
    'outdoor cycling': '户外单车', 'indoor cycling': '室内单车',
    'hiking': '徒步', 'rowing': '划船', 'yoga': '瑜伽', 'pilates': '普拉提',
    'elliptical': '椭圆机', 'stair climbing': '爬楼梯', 'stairclimbing': '爬楼梯',
    'traditional strength training': '传统力量训练', 'functional strength training': '功能性力量训练',
    'strength training': '力量训练', 'strengthtraining': '力量训练', 'strength': '力量训练',
    'high intensity interval training': '高强度间歇训练', 'hiit': '高强度间歇训练',
    'cross training': '交叉训练', 'dance': '舞蹈', 'basketball': '篮球',
    'soccer': '足球', 'football': '足球', 'tennis': '网球', 'badminton': '羽毛球',
    'table tennis': '乒乓球', 'jump rope': '跳绳', 'core training': '核心训练',
    'cooldown': '放松训练', 'flexibility': '柔韧性训练', 'other': '其他训练',
}


def font(size, bold=False):
    for path in (BOLD_FONT_PATHS if bold else FONT_PATHS):
        if Path(path).is_file():
            return ImageFont.truetype(path, size * RENDER_SCALE)
    return ImageFont.load_default(size=size * RENDER_SCALE)


class ScaledDraw:
    """Draw in layout coordinates onto a supersampled Pillow canvas."""
    def __init__(self, image):
        self.draw = ImageDraw.Draw(image)

    @staticmethod
    def coords(value):
        return tuple(ScaledDraw.coords(item) if isinstance(item, (list, tuple)) else item * RENDER_SCALE for item in value)

    def line(self, xy, fill=None, width=0, joint=None):
        self.draw.line(self.coords(xy), fill=fill, width=round(width * RENDER_SCALE), joint=joint)

    def rounded_rectangle(self, xy, radius=0, fill=None, outline=None, width=1):
        self.draw.rounded_rectangle(self.coords(xy), radius=radius * RENDER_SCALE, fill=fill, outline=outline, width=width * RENDER_SCALE)

    def ellipse(self, xy, fill=None):
        self.draw.ellipse(self.coords(xy), fill=fill)

    def text(self, xy, text, **kwargs):
        if 'stroke_width' in kwargs:
            kwargs['stroke_width'] *= RENDER_SCALE
        self.draw.text(self.coords(xy), text, **kwargs)


def glass_card(image, box):
    """Blur the underlying route within a rounded translucent panel."""
    x0, y0, x1, y1 = (round(value * RENDER_SCALE) for value in box)
    size = (x1 - x0, y1 - y0)
    background = image.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(12 * RENDER_SCALE)).convert('RGBA')
    background = Image.alpha_composite(background, Image.new('RGBA', size, (20, 42, 39, 145)))
    mask = Image.new('L', size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=18 * RENDER_SCALE, fill=255)
    image.paste(background.convert('RGB'), (x0, y0), mask)
    draw = ScaledDraw(image)
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, outline='#628879', width=2)
    draw.rounded_rectangle((left + 2, top + 2, right - 2, bottom - 2), radius=16, outline='#314e47', width=1)
    draw.line((left + 20, top + 2, right - 20, top + 2), fill='#84b8a0', width=1)


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (ValueError, OverflowError):
        return None


def val(row, *names):
    return next((row[k] for k in names if k in row and row[k] is not None), None)


def series(rows, names, transform=lambda v: v):
    points = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        t = timestamp(val(row, 'Time', 'time', 'timestamp'))
        v = number(val(row, *names))
        if t is not None and v is not None:
            v = transform(v)
            if v is not None and math.isfinite(v):
                points.append((t, v))
    return sorted(points)


def smooth_line(draw, points, color, width=4):
    """Ease between sampled points without overshooting the observed values."""
    if len(points) < 2:
        return
    result = [points[0]]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        for i in range(1, 9):
            t = i / 8
            ease = t * t * (3 - 2 * t)
            result.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * ease))
    draw.line(result, fill=color, width=width, joint='curve')


def chart(draw, top, title, unit, points, color, pace=False):
    left, right, bottom = 90, 935, top + 322
    draw.rounded_rectangle((40, top, 960, top + 365), 24, fill='#172127', outline='#293b3b', width=2)
    draw.text((75, top + 26), title, font=font(30), fill=INK)
    draw.text((right, top + 31), unit, font=font(20), fill=MUTED, anchor='ra')
    area_top = top + 88
    low, high = min(p[1] for p in points), max(p[1] for p in points)
    pad = max((high - low) * .12, 0.5)
    low, high = low - pad, high + pad
    t0, t1 = points[0][0], points[-1][0]
    for i in range(3):
        y = area_top + (bottom - area_top) * i / 2
        v = high - (high - low) * i / 2
        label = f'{int(v)}' if not pace else f'{int(v)//60}:{int(v)%60:02d}'
        draw.line((left, y, right, y), fill='#2b3d3f', width=2)
        draw.text((left - 10, y), label, fill=MUTED, font=font(18), anchor='rm')
    span = max(t1 - t0, 1)
    # Gap boundaries prevent a missing section from becoming a fabricated line.
    chunk = []
    prev = None
    for t, value in points:
        if prev is not None and t - prev > 180:
            smooth_line(draw, chunk, color)
            chunk = []
        chunk.append((left + (t - t0) / span * (right - left), bottom - (value - low) / (high - low) * (bottom - area_top)))
        prev = t
    smooth_line(draw, chunk, color)
    draw.text((left, top + 337), '0 分钟', fill=MUTED, font=font(19))
    draw.text((right, top + 337), f'{round(span / 60)} 分钟', fill=MUTED, font=font(19), anchor='ra')


def combined_chart(draw, top, heart, speed):
    left, right, area_top, bottom = 100, 900, top + 90, top + 322
    draw.rounded_rectangle((40, top, 960, top + 365), 24, fill='#172127', outline='#293b3b', width=2)
    draw.text((75, top + 25), '心率与速度', font=font(30), fill=INK)
    draw.text((right, top + 30), '心率 · 次/分钟     速度 · 公里/小时', font=font(20), fill=MUTED, anchor='ra')
    t0, t1 = min(heart[0][0], speed[0][0]), max(heart[-1][0], speed[-1][0])
    span = max(t1 - t0, 1)
    low, high = min(v for _, v in heart), max(v for _, v in heart)
    pad = max((high - low) * .12, 2)
    low, high = low - pad, high + pad
    max_speed = max(v for _, v in speed) * 1.1
    for i in range(3):
        y = area_top + (bottom - area_top) * i / 2
        draw.line((left, y, right, y), fill='#2b3d3f', width=2)
        draw.text((left - 10, y), str(round(high - (high - low) * i / 2)), fill='#eb9fa2', font=font(18), anchor='rm')
        draw.text((right + 10, y), f'{max_speed * (1 - i / 2):.1f}', fill='#8ca6e8', font=font(18), anchor='lm')
    # Average only existing samples in each bucket; empty buckets stay empty.
    buckets = {}
    for t, value in speed:
        index = min(47, int((t - t0) / span * 48))
        total, count = buckets.get(index, (0, 0))
        buckets[index] = (total + value, count + 1)
    step = (right - left) / 48
    for index, (total, count) in buckets.items():
        height = (total / count) / max_speed * (bottom - area_top)
        x = left + index * step + 2
        draw.rounded_rectangle((x, bottom - height, x + step - 4, bottom), radius=5, fill='#3d5685')
    chunk, prev = [], None
    for t, value in heart:
        if prev is not None and t - prev > 180:
            smooth_line(draw, chunk, '#f18f91', 4)
            chunk = []
        chunk.append((left + (t - t0) / span * (right - left), bottom - (value - low) / (high - low) * (bottom - area_top)))
        prev = t
    smooth_line(draw, chunk, '#f18f91', 4)
    draw.text((left, top + 337), '0 分钟', fill=MUTED, font=font(19))
    draw.text((right, top + 337), f'{round(span / 60)} 分钟', fill=MUTED, font=font(19), anchor='ra')


def make_report(detail):
    if not isinstance(detail, dict):
        raise ValueError('训练详情不可用，无法生成报告')
    route = val(detail, 'RouteData', 'route_data') or []
    hr = val(detail, 'HeartRateData', 'heart_rate_data') or []
    route = route if isinstance(route, list) else []
    hr = hr if isinstance(hr, list) else []
    coords = []
    for row in route:
        if not isinstance(row, dict):
            continue
        lat, lon = number(val(row, 'Latitude', 'latitude')), number(val(row, 'Longitude', 'longitude'))
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
            coords.append((lon, lat))
    heart = series(hr, ('AvgBPM', 'avg_bpm', 'avg'))
    heart = [(t, v) for t, v in heart if 30 <= v <= 250]
    pace = series(route, ('Speed', 'speed'), lambda v: 1000 / v if 0.5 <= v <= 12 else None)
    speed = series(route, ('Speed', 'speed'), lambda v: v * 3.6 if 0.5 <= v <= 12 else None)
    charts = [(name, unit, data, color, is_pace) for name, unit, data, color, is_pace in [
        ('心率', '次/分钟', heart, '#eb6c72', False), ('配速', '分钟 / 公里', pace, '#6886df', True),
        ] if len(data) >= 2 and data[-1][0] > data[0][0]]
    if len(heart) >= 2 and heart[-1][0] > heart[0][0] and len(speed) >= 2 and speed[-1][0] > speed[0][0]:
        charts = [('心率与速度', '', (heart, speed), '', False)] + [item for item in charts if item[0] not in ('心率', '配速')]
    original_name = str(val(detail, 'Name', 'name') or '训练记录').strip()
    lookup = original_name.casefold().removeprefix('hkworkoutactivitytype').strip()
    name = WORKOUT_NAMES.get(lookup, original_name)[:18]
    indoor = val(detail, 'IsIndoor', 'is_indoor', 'isIndoor')
    if type(indoor) is bool and name in ('跑步', '步行', '单车'):
        name = ('室内' if indoor else '户外') + name
    start = str(val(detail, 'StartTime', 'start_time') or '')[:16].replace('T', ' ')
    duration = number(val(detail, 'DurationSec', 'duration_sec'))
    distance = number(val(detail, 'Distance', 'distance'))
    distance_unit = str(val(detail, 'DistanceUnits', 'distance_units') or '')
    hr_avg = number(val(detail, 'AvgHeartRate', 'avg_heart_rate'))
    metrics = []
    if duration is not None and duration >= 0:
        seconds = int(duration)
        formatted = f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}' if seconds >= 3600 else f'{seconds // 60:02d}:{seconds % 60:02d}'
        metrics.append(('时长', formatted))
    if distance is not None: metrics.append(('距离', f'{distance:g} {distance_unit}'.strip()))
    if hr_avg is not None: metrics.append(('平均心率', f'{math.floor(hr_avg + 0.5)} 次/分钟'))
    active = number(val(detail, 'ActiveEnergyBurned', 'active_energy_burned'))
    total = number(val(detail, 'TotalEnergy', 'total_energy'))
    active_unit = str(val(detail, 'ActiveEnergyUnits', 'active_energy_units') or '')
    total_unit = str(val(detail, 'TotalEnergyUnits', 'total_energy_units') or '')
    if active is not None:
        is_kcal = active_unit.strip().lower() in ('kcal', 'cal', 'calorie', 'calories', '千卡', '大卡')
        shown = str(math.floor(active + 0.5)) if is_kcal else f'{active:g}'
        metrics.append(('活动消耗', f"{shown} {'千卡' if is_kcal else active_unit}".strip()))
    if total is not None: metrics.append(('总消耗', f'{total:g} {total_unit}'.strip()))
    maximum = number(val(detail, 'MaxHeartRate', 'max_heart_rate'))
    minimum = number(val(detail, 'MinHeartRate', 'min_heart_rate'))
    ascent = number(val(detail, 'ElevationUp', 'elevation_up'))
    if maximum is not None: metrics.append(('最高心率', f'{maximum:g} 次/分钟'))
    if minimum is not None: metrics.append(('最低心率', f'{minimum:g} 次/分钟'))
    if ascent is not None: metrics.append(('累计爬升', f'{ascent:g} m'))
    if total_unit.strip().lower() in ('kcal', 'cal', 'calorie', 'calories', '千卡', '大卡') and total is not None:
        metrics = [(label, f'{total:g} 千卡' if label == '总消耗' else value) for label, value in metrics]
    metrics = metrics[:8]
    rows = math.ceil(len(metrics) / 4)
    header_bottom = 260 + rows * 130 + 35 if rows else 250
    chart_top = header_bottom + 30
    canvas_height = chart_top + 390 * len(charts) + 10
    image = Image.new('RGB', (W * RENDER_SCALE, canvas_height * RENDER_SCALE), BG)
    draw = ScaledDraw(image)
    draw.rounded_rectangle((40, 40, 960, header_bottom), 28, fill='#142925', outline='#305044', width=2)
    if len(coords) >= 2:
        coslat = max(.05, abs(math.cos(math.radians(sum(point[1] for point in coords) / len(coords)))))
        xy = [(lon * coslat, -lat) for lon, lat in coords]
        xmin, xmax = min(x for x, y in xy), max(x for x, y in xy)
        ymin, ymax = min(y for x, y in xy), max(y for x, y in xy)
        width, height = 790, max(100, header_bottom - 120)
        scale = min(width / max(xmax - xmin, 1e-8), height / max(ymax - ymin, 1e-8))
        right, bottom = 915, header_bottom - 48
        points = [(right - (xmax - x) * scale, bottom - (ymax - y) * scale) for x, y in xy]
        glow = Image.new('RGBA', image.size, (0, 0, 0, 0))
        glow_draw = ScaledDraw(glow)
        glow_draw.line(points, fill=(69, 255, 170, 160), width=28, joint='curve')
        glow = glow.filter(ImageFilter.GaussianBlur(19 * RENDER_SCALE))
        mask = Image.new('L', image.size, 0)
        ScaledDraw(mask).rounded_rectangle((42, 42, 958, header_bottom - 2), 26, fill=255)
        image.paste(glow, (0, 0), Image.composite(glow.getchannel('A'), Image.new('L', image.size), mask))
        draw = ScaledDraw(image)
        draw.line(points, fill='#54dba1', width=9, joint='curve')
        draw.line(points, fill='#d0ffdf', width=3, joint='curve')
        x, y = points[0]; draw.ellipse((x-7, y-7, x+7, y+7), fill='#dcffe8')
        x, y = points[-1]; draw.ellipse((x-7, y-7, x+7, y+7), fill='#ffd29e')
    draw.text((80, 72), '运动训练报告', fill='#74e1ad', font=font(23))
    draw.text((80, 115), name, fill='white', font=font(48))
    if start:
        draw.text((915, 80), start, fill='#c6e4d8', font=font(23), anchor='ra')
    if rows:
        glass_card(image, (62, 245, 938, header_bottom - 18))
        draw = ScaledDraw(image)
        for i, (label, value) in enumerate(metrics):
            x, y = 72 + (i % 4) * 215, 255 + (i // 4) * 130
            draw.text((x + 14, y + 15), label, fill='#c2dbd0', font=font(21))
            draw.text((x + 14, y + 54), value, fill='#f2f8f4', font=font(26, bold=True))
    for i, (title, unit, data, color, is_pace) in enumerate(charts):
        if title == '心率与速度':
            combined_chart(draw, chart_top + i * 390, *data)
        else:
            chart(draw, chart_top + i * 390, title, unit, data, color, is_pace)
    output = io.BytesIO()
    image = image.resize((round(W * OUTPUT_SCALE), round(canvas_height * OUTPUT_SCALE)), Image.Resampling.LANCZOS)
    image.save(output, format='PNG', optimize=True)
    return output.getvalue(), {'route': len(coords) >= 2, 'charts': [item[0] for item in charts]}
