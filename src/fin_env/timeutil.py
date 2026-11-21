"""Timestamps: ISO-8601 with fixed offsets (no DST), no wall clock."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


def parse_offset(text: str) -> timezone:
    sign = -1 if text[0] == "-" else 1
    hh, mm = int(text[1:3]), int(text[4:6])
    return timezone(sign * timedelta(hours=hh, minutes=mm))


def fmt_offset(minutes: int) -> str:
    sign = "-" if minutes < 0 else "+"
    m = abs(minutes)
    return f"{sign}{m // 60:02d}:{m % 60:02d}"


def parse_ts(text: str) -> datetime:
    if not TS_RE.match(text):
        raise ValueError("bad timestamp")
    return datetime.fromisoformat(text)


def fmt_ts(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def local_dt(text: str, tz: str) -> datetime:
    return parse_ts(text).astimezone(parse_offset(tz))


def local_date(text: str, tz: str) -> date:
    return local_dt(text, tz).date()


def period_of(text: str, tz: str) -> str:
    d = local_date(text, tz)
    return f"{d.year:04d}-{d.month:02d}"


def make_ts(d: date, hour: int, minute: int, tz: str) -> str:
    return fmt_ts(datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=parse_offset(tz)))


def month_range(period_start: str) -> tuple[date, date]:
    start = date.fromisoformat(period_start)
    nxt = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, nxt - timedelta(days=1)


def period_label(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def next_period_label(period: str) -> str:
    y, m = int(period[:4]), int(period[5:7])
    return f"{y + (m == 12):04d}-{m % 12 + 1:02d}"
