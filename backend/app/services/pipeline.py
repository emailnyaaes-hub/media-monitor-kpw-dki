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
from app.services.matching import excluded, matched_terms, passes_saved_queries
from app.services.urls import canonical_url, is_public_article

log = logging.getLogger("bi.ingest")
ingest_lock = threading.Lock()

CITIES = [
    "Kepulauan Seribu",
    "Jakarta Pusat",
    "Jakarta Utara",
    "Jakarta Barat",
    "Jakarta Selatan",
    "Jakarta Timur",
]


def ingest(db: Session) -> dict:
    if not ingest_lock.acquire(blocking=False):
        return {"status": "sedang_berjalan", "added": 0, "skipped": 0, "rejected": 0, "invalid_url": 0, "alerts": 0}
    started = now_wib()
    try:
        since = _since(db)
        keywords = db.query(Keyword).all()
        queries = db.query(SavedQuery).all()
        from app.services.blocklist import load_rules

        rules = load_rules(db)
        db.commit()
        log.info("Pengambilan mulai. Jendela sejak %s", since.isoformat(timespec="minutes"))
        reports = collect_reports(since, rules)
        added = skipped = rejected = invalid = 0
        summaries = []
        any_ok = False
        for report in reports:
            result = _store_report(db, report, keywords, queries, rules, started)
            added += result["added"]
            skipped += result["skipped"]
            rejected += result["rejected"]
            invalid += result["invalid_url"]
            any_ok = any_ok or report.status == "berhasil"
            summaries.append(result["summary"])
            log.info("%s | %s | ditemukan %s | baru %s | %s", report.name, report.status, result["summary"]["found"], result["added"], report.message)
        created = rebuild_issues(db) if any_ok or added else 0
        alerts = evaluate_rules(db) if any_ok or added else 0
        advice = {"created": 0, "updated": 0, "expired": 0}
        if any_ok or added:
            from app.services.dss import refresh_advices

            advice = refresh_advices(db)
        if any_ok:
            db.merge(AppMeta(key="last_ingest_at", value=now_wib().isoformat(timespec="minutes")))
            db.merge(AppMeta(key="data_mode", value="live"))
            db.commit()
        log.info("Pengambilan selesai. baru=%s dilewati=%s ditolak=%s url_gagal=%s", added, skipped, rejected, invalid)
        return {
            "status": "selesai",
            "added": added,
            "skipped": skipped,
            "rejected": rejected,
            "invalid_url": invalid,
            "alerts": alerts,
            "issues": created,
            "advices": advice,
            "connectors": summaries,
        }
    finally:
        ingest_lock.release()


def status_payload(db: Session) -> dict:
    from app.scheduler import next_run_wib

    last = db.get(AppMeta, "last_ingest_at")
    rows = db.query(ConnectorRun).order_by(ConnectorRun.finished_at.desc(), ConnectorRun.id.desc()).limit(120).all()
    latest: dict[str, ConnectorRun] = {}
    for row in rows:
        latest.setdefault(row.connector, row)
    return {
        "last_updated": last.value if last else None,
        "next_update": next_run_wib(),
        "running": ingest_lock.locked(),
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
            for row in latest.values()
        ],
    }


def retag(db: Session) -> int:
    keywords = db.query(Keyword).all()
    count = 0
    for row in db.query(Mention).all():
        row.keyword_matches = json.dumps(
            matched_terms(f"{row.title}\n{row.text}", keywords),
            ensure_ascii=False,
        )
        count += 1
    db.commit()
    return count


def _since(db: Session) -> datetime:
    last = db.get(AppMeta, "last_ingest_at")
    now = now_wib()
    if last is None or not last.value:
        return now - timedelta(days=3)
    try:
        previous = datetime.fromisoformat(last.value)
    except ValueError:
        return now - timedelta(days=3)
    return max(previous - timedelta(hours=6), now - timedelta(days=14))


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
    if excluded(match_text, keywords) or not matched_terms(match_text, keywords) or not passes_saved_queries(match_text, queries):
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
    hay = full.casefold()
    db.add(
        Mention(
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
            needs_verification="hoaks" in hay or "penipuan" in hay,
            verification_note="Judul atau cuplikan memuat kata hoaks atau penipuan. Buka sumber asli sebelum menindaklanjuti." if "hoaks" in hay or "penipuan" in hay else "",
            is_kpw="kpw" in hay or "dki" in hay or "jakarta" in hay,
            location=next((city for city in CITIES if city.casefold() in hay), ""),
            human_corrected=False,
            quotes_bi=cites_bi(title, text),
            status="baru",
        )
    )
    db.commit()
    return "added"
