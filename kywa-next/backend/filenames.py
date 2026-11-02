"""Human-readable storage and download names, always using Korea time."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')


def korea_time(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=KST) if parsed.tzinfo is None else parsed.astimezone(KST)


def component(value):
    return re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', value).strip(' .') or 'KYWA'


def photo_filename(facility, created_at, after=False):
    return f"{component(facility)}_{'개선후_' if after else ''}{korea_time(created_at):%Y%m%d_%H%M%S}.jpg"


def report_filename(facility, format, created_at, institution='KYWA'):
    if format not in {'pdf', 'xlsx', 'hwpx'}:
        raise ValueError('Unsupported report format')
    return f"{component(facility or institution)}_위험성평가_{korea_time(created_at):%Y%m%d}.{format}"
