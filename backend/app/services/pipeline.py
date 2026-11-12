"""Mengambil sumber nyata, membuang URL yang tidak sah, lalu mengklasifikasi ulang."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.connectors.live import FetchReport, collect_reports
from app.models import AppMeta, ConnectorRun, Keyword, Mention, SavedQuery
from app.nlp import analyze
from app.services.alerts import evaluate_rules
from app.services.clock import now_wib
from app.services.clustering import rebuild_issues
from app.services.matching import eligible_for_ingest, matched_terms
from app.services.urls import canonical_url, is_public_article

log = logging.getLogger("bi.ingest")
ingest_lock = threading.Lock()
INGEST_STALE_MINUTES = 6

CITIES = [
    "Kepulauan Seribu",
    "Jakarta Pusat",
    "Jakarta Utara",
    "Jakarta Barat",
    "Jakarta Selatan",
    "Jakarta Timur",
]


def start_ingest(mode: str = "cepat") -> dict:
    """Mulai pengambilan di thread terpisah agar request HTTP tidak digantung Vercel."""
    if mode not in {"cepat", "penuh"}:
        mode = "cepat"
    if ingest_lock.locked():
        return {"status": "sedang_berjalan", "mode": mode, "added": 0, "message": "Pengambilan lain masih berjalan."}

    def runner() -> None:
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            ingest(db, mode=mode)
        except Exception:
            log.exception("Pengambilan latar gagal")
        finally:
            db.close()

    threading.Thread(target=runner, name=f"ingest-{mode}", daemon=True).start()
    return {
        "status": "dimulai",
        "mode": mode,
        "added": 0,
        "message": "Pengambilan dimulai. Status akan berubah setelah sumber selesai dibaca.",
    }


def _set_running(db: Session, active: bool) -> None:
    db.merge(AppMeta(key="ingest_running_since", value=now_wib().isoformat(timespec="minutes") if active else ""))
    db.commit()


def _running_stale(db: Session) -> bool:
    row = db.get(AppMeta, "ingest_running_since")
    if row is None or not (row.value or "").strip():
        return False
    try:
        since = datetime.fromisoformat(row.value)
    except ValueError:
        return True
    return now_wib() - since > timedelta(minutes=INGEST_STALE_MINUTES)


def ingest_running(db: Session) -> bool:
    if _running_stale(db):
        _set_running(db, False)
        return False
    row = db.get(AppMeta, "ingest_running_since")
    return bool(row and (row.value or "").strip())


def ingest(db: Session, mode: str = "cepat") -> dict:
    if mode not in {"cepat", "penuh"}:
        mode = "cepat"
    if ingest_running(db) and not _running_stale(db):
        return {"status": "sedang_berjalan", "mode": mode, "added": 0, "skipped": 0, "rejected": 0, "invalid_url": 0, "alerts": 0}
    if _running_stale(db):
        _set_running(db, False)
    if not ingest_lock.acquire(blocking=False):
        return {"status": "sedang_berjalan", "mode": mode, "added": 0, "skipped": 0, "rejected": 0, "invalid_url": 0, "alerts": 0}
    started = now_wib()
    _set_running(db, True)
    try:
        since = _since(db)
        keywords = db.query(Keyword).all()
        queries = db.query(SavedQuery).all()
        from app.services.blocklist import load_rules

        rules = load_rules(db)
        db.commit()
        log.info("Pengambilan %s mulai. Jendela sejak %s", mode, since.isoformat(timespec="minutes"))
        added = skipped = rejected = invalid = 0
        summaries = []
        any_ok = False

        def _consume(report) -> None:
            nonlocal added, skipped, rejected, invalid, any_ok
            if report.status == "tidak_tersedia":
                summaries.append(
                    {"name": report.name, "status": report.status, "found": 0, "added": 0, "message": report.message[:300]}
                )
                return
            result = _store_report(db, report, keywords, queries, rules, started)
            added += result["added"]
            skipped += result["skipped"]
            rejected += result["rejected"]
            invalid += result["invalid_url"]
            any_ok = any_ok or report.status == "berhasil"
            summaries.append(result["summary"])
            log.info(
                "%s | %s | ditemukan %s | baru %s | %s",
                report.name,
                report.status,
                result["summary"]["found"],
                result["added"],
                report.message,
            )

        # Tematik dulu dan langsung disimpan — bila Vercel timeout, rubrik tetap terisi.
        if mode == "cepat":
            import time
            from concurrent.futures import ThreadPoolExecutor, as_completed

            from app.connectors.live import (
                fetch_google_kpw_dki,
                fetch_google_kpw_provinsi,
                fetch_google_pemprov_dki,
                fetch_pemprov_portal,
            )

            # Portal resmi Pemprov dulu — hard cap agar tidak menggantung.
            try:
                _consume(fetch_pemprov_portal(deadline=time.monotonic() + 16))
            except Exception as exc:
                log.exception("Portal Pemprov gagal: %s", exc)

            theme_deadline = time.monotonic() + 20
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(fetch_google_pemprov_dki, theme_deadline),
                    pool.submit(fetch_google_kpw_dki, theme_deadline),
                    pool.submit(fetch_google_kpw_provinsi, theme_deadline),
                ]
                try:
                    for future in as_completed(futures, timeout=22):
                        try:
                            _consume(future.result())
                        except Exception as exc:
                            log.exception("Arsip tematik gagal: %s", exc)
                except TimeoutError:
                    log.warning("Batas waktu arsip tematik Google habis; lanjut RSS.")
            # Mode cepat: skip RSS berat bila sudah dapat Pemprov, hemat waktu Vercel.
            reports = []
            if added < 3:
                reports = collect_reports(since, rules, mode=mode, include_thematic=False)
        else:
            import time as _time

            from app.connectors.live import fetch_pemprov_portal

            try:
                _consume(fetch_pemprov_portal(deadline=_time.monotonic() + 20))
            except Exception as exc:
                log.exception("Portal Pemprov gagal: %s", exc)
            reports = collect_reports(since, rules, mode=mode, include_thematic=True)
        for report in reports:
            _consume(report)
        # Mode cepat: simpan mention saja. Susunan isu/saran ditunda agar UI tidak timeout.
        created = 0
        alerts = 0
        advice = {"created": 0, "updated": 0, "expired": 0}
        if mode == "penuh" and (any_ok or added):
            created = rebuild_issues(db)
            alerts = evaluate_rules(db)
            from app.services.dss import refresh_advices

            advice = refresh_advices(db)
        elif mode == "cepat" and added:
            created = rebuild_issues(db)
        db.merge(AppMeta(key="last_ingest_at", value=now_wib().isoformat(timespec="minutes")))
        if any_ok or added:
            db.merge(AppMeta(key="data_mode", value="live"))
        db.commit()
        log.info("Pengambilan %s selesai. baru=%s dilewati=%s ditolak=%s url_gagal=%s", mode, added, skipped, rejected, invalid)
        return {
            "status": "selesai",
            "mode": mode,
            "added": added,
            "skipped": skipped,
            "rejected": rejected,
            "invalid_url": invalid,
            "alerts": alerts,
            "issues": created,
            "advices": advice,
            "connectors": summaries,
        }
    except Exception as exc:
        log.exception("Pengambilan gagal")
        return {
            "status": "gagal",
            "mode": mode,
            "added": 0,
            "skipped": 0,
            "rejected": 0,
            "invalid_url": 0,
            "alerts": 0,
            "error": f"{exc.__class__.__name__}: {exc}",
        }
    finally:
        try:
            _set_running(db, False)
        except Exception:
            log.exception("Gagal mengosongkan penanda pengambilan")
        ingest_lock.release()


def needs_refresh(db: Session) -> bool:
    """True bila pembaruan terakhir lebih dari 2 jam atau belum pernah ada."""
    if ingest_running(db):
        return False
    last = db.get(AppMeta, "last_ingest_at")
    now = now_wib()
    if last is None or not last.value:
        return True
    try:
        previous = datetime.fromisoformat(last.value)
    except ValueError:
        return True
    return now - previous >= timedelta(hours=2)


def status_payload(db: Session) -> dict:
    import os

    from app.scheduler import next_run_wib

    last = db.get(AppMeta, "last_ingest_at")
    if os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV"):
        schedule = (
            "Vercel 1×/hari (~08.00 WIB) + GitHub Actions tiap 2 jam bila workflow & CRON_SECRET aktif"
        )
    else:
        schedule = "setiap 2 jam (penjadwal server)"
    rows = db.query(ConnectorRun).order_by(ConnectorRun.finished_at.desc(), ConnectorRun.id.desc()).limit(120).all()
    latest: dict[str, ConnectorRun] = {}
    for row in rows:
        latest.setdefault(row.connector, row)
    cutoff = None
    if last and last.value:
        try:
            cutoff = datetime.fromisoformat(last.value) - timedelta(hours=2)
        except ValueError:
            cutoff = None
    connector_rows = list(latest.values())
    if cutoff is not None:
        connector_rows = [row for row in connector_rows if row.finished_at >= cutoff]
    connector_rows = [
        row
        for row in connector_rows
        if row.connector not in {"Threads API"} and row.status != "tidak_tersedia"
    ]
    return {
        "last_updated": last.value if last else None,
        "next_update": next_run_wib(),
        "schedule": schedule,
        "needs_refresh": needs_refresh(db),
        "running": ingest_running(db),
        "timezone": "Asia/Jakarta",
        "connectors": [
            {
                "name": row.connector,
                "status": row.status,
                "message": row.message,
                "found": row.found,
                "added": row.added,
                "finished_at": row.finished_at.isoformat(timespec="minutes"),
            }
            for row in connector_rows
        ],
    }


def retag(db: Session) -> int:
    from app.services.mention_brief import build_mention_brief
    from app.services.news_sections import classify_feed_section

    keywords = db.query(Keyword).all()
    count = 0
    for row in db.query(Mention).all():
        row.keyword_matches = json.dumps(
            matched_terms(f"{row.title}\n{row.text}", keywords),
            ensure_ascii=False,
        )
        row.brief = build_mention_brief(row)
        row.feed_section = classify_feed_section(row)
        count += 1
    db.commit()
    return count


def _since(db: Session) -> datetime:
    """Jendela RSS/umum: hingga 90 hari agar berita lama relevan tetap bisa masuk."""
    last = db.get(AppMeta, "last_ingest_at")
    now = now_wib()
    horizon = now - timedelta(days=90)
    if last is None or not last.value:
        return horizon
    try:
        previous = datetime.fromisoformat(last.value)
    except ValueError:
        return horizon
    return max(previous - timedelta(hours=6), horizon)


def _store_report(db: Session, report: FetchReport, keywords: list, queries: list, rules: list, started: datetime) -> dict:
    added = skipped = rejected = invalid = 0
    if report.status == "berhasil":
        for item in report.items:
            outcome = _consider(db, item, keywords, queries, rules)
            if outcome == "added":
                added += 1
            elif outcome == "skipped":
                skipped += 1
            elif outcome == "rejected":
                rejected += 1
            elif outcome == "invalid":
                invalid += 1
        db.commit()
    finished = now_wib()
    message = report.message
    if invalid:
        message = f"{message} {invalid} item dibuang karena URL penerbit tidak dapat dibuka."
    db.add(
        ConnectorRun(
            connector=report.name,
            status=report.status,
            message=message[:1000],
            found=len(report.items),
            added=added,
            started_at=started,
            finished_at=finished,
        )
    )
    db.commit()
    return {
        "added": added,
        "skipped": skipped,
        "rejected": rejected,
        "invalid_url": invalid,
        "summary": {"name": report.name, "status": report.status, "found": len(report.items), "added": added, "message": message[:300]},
    }


def _consider(db: Session, item, keywords: list, queries: list, rules: list) -> str:
    url = canonical_url(item.url)
    if not url or "news.google.com" in url or "contoh.media-monitor.local" in url:
        return "invalid"
    title = (item.title or "").strip()[:300]
    text = (item.text or "").strip()
    if len(text) > 360:
        text = text[:360].rsplit(" ", 1)[0] + "…"
    if not text:
        text = "Cuplikan tidak tersedia di feed. Buka sumber asli."
    full = f"{title}\n{text}"
    match_text = f"{item.author_name}\n{item.source_name}\n{full}"
    match_text = match_text.casefold().replace("#", " ").replace("sobatrupiah", "sobat rupiah")
    from app.services.blocklist import cites_bi, is_blocked

    if is_blocked(url, item.author_handle, item.author_name, item.source_name, title, rules):
        return "rejected"
    if not eligible_for_ingest(match_text, keywords, queries):
        return "rejected"
    digest = hashlib.sha256(url.encode()).hexdigest()
    if db.query(Mention).filter((Mention.content_hash == digest) | (Mention.url == url)).first():
        db.commit()
        return "skipped"
    db.commit()
    if not is_public_article(url):
        return "invalid"
    result = analyze(
        full,
        reach=0,
        source_tier=item.source_tier,
        velocity=0,
        has_public_figure=False,
        credibility=item.credibility,
    )
    from app.services.mention_brief import build_mention_brief

    hay = full.casefold()
    needs_verification = "hoaks" in hay or "penipuan" in hay
    quotes_bi = cites_bi(title, text)
    mention_kwargs = dict(
        content_hash=digest,
        source_name=item.source_name[:120],
        source_tier=item.source_tier,
        platform=item.platform,
        url=url,
        author_name=(item.author_name or item.source_name)[:120],
        author_handle=(item.author_handle or "")[:120],
        published_at=item.published_at,
        title=title,
        text=text,
        language="id",
        likes=0,
        shares=0,
        comments=0,
        reach_estimate=0,
        keyword_matches=json.dumps(matched_terms(match_text, keywords), ensure_ascii=False),
        sentiment=result["sentiment"],
        sentiment_score=result["sentiment_score"],
        stance=result["stance"],
        confidence=result["confidence"],
        rationale=result["rationale"],
        category=result["category"],
        risk_score=result["risk_score"],
        policy_relevance=result["policy_relevance"],
        policy_tags=json.dumps(result["policy_tags"], ensure_ascii=False),
        spread_velocity=0,
        impact_level="rendah",
        credibility=item.credibility,
        has_public_figure=False,
        needs_verification=needs_verification,
        verification_note=(
            "Judul atau cuplikan memuat kata hoaks atau penipuan. Buka sumber asli sebelum menindaklanjuti."
            if needs_verification
            else ""
        ),
        is_kpw="kpw" in hay or "dki" in hay or "jakarta" in hay,
        location=next((city for city in CITIES if city.casefold() in hay), ""),
        human_corrected=False,
        quotes_bi=quotes_bi,
        status="baru",
        brief="",
    )
    stub = Mention(**mention_kwargs)
    from app.services.news_sections import classify_feed_section

    mention_kwargs["feed_section"] = classify_feed_section(stub)
    stub.feed_section = mention_kwargs["feed_section"]
    mention_kwargs["brief"] = build_mention_brief(stub)
    db.add(Mention(**mention_kwargs))
    db.commit()
    return "added"
