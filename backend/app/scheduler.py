"""Pembaruan otomatis setiap 2 jam, zona Asia/Jakarta."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.constants import TIMEZONE_NAME
from app.database import SessionLocal
from app.services.pipeline import ingest

log = logging.getLogger("bi.scheduler")
WIB = ZoneInfo(TIMEZONE_NAME)
scheduler = BackgroundScheduler(timezone=WIB)


def start_scheduler() -> None:
    import os

    if os.environ.get("BI_DISABLE_SCHEDULER") == "1":
        return
    if scheduler.running:
        return
    scheduler.add_job(
        _run,
        trigger="interval",
        hours=2,
        id="refresh",
        replace_existing=True,
        next_run_time=datetime.now(WIB) + timedelta(seconds=15),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info("Penjadwal aktif. Berikutnya %s", next_run_wib())


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def next_run_wib() -> str | None:
    if not scheduler.running:
        return None
    job = scheduler.get_job("refresh")
    if job is None or job.next_run_time is None:
        return None
    return job.next_run_time.astimezone(WIB).replace(tzinfo=None).isoformat(timespec="minutes")


def _run() -> None:
    db = SessionLocal()
    try:
        ingest(db)
    except Exception:
        log.exception("Putaran terjadwal gagal")
    finally:
        db.close()
