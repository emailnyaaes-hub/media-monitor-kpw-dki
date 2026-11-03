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

    if os.environ.get("BI_DISABLE_SCHEDULER") == "1" or os.environ.get("VERCEL") == "1":
        # Di Vercel pakai Cron Jobs (GET /api/cron/ingest), bukan proses background.
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
    import os

    if scheduler.running:
        job = scheduler.get_job("refresh")
        if job is not None and job.next_run_time is not None:
            return job.next_run_time.astimezone(WIB).replace(tzinfo=None).isoformat(timespec="minutes")
    # Di Vercel, penjadwal proses dimatikan. GitHub Actions memanggil /api/cron/ingest tiap 2 jam UTC.
    if os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV"):
        now_utc = datetime.now(ZoneInfo("UTC")).replace(minute=0, second=0, microsecond=0)
        hours = 2 - (now_utc.hour % 2)
        if hours == 0:
            hours = 2
        nxt = now_utc + timedelta(hours=hours)
        return nxt.astimezone(WIB).replace(tzinfo=None).isoformat(timespec="minutes")
    return None


def _run() -> None:
    db = SessionLocal()
    try:
        ingest(db)
    except Exception:
        log.exception("Putaran terjadwal gagal")
    finally:
        db.close()
