"""Waktu operasional dalam WIB, disimpan sebagai datetime tanpa zona."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.constants import TIMEZONE_NAME

WIB = ZoneInfo(TIMEZONE_NAME)


def now_wib() -> datetime:
    return datetime.now(WIB).replace(tzinfo=None)
