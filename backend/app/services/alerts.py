"""Menjalankan aturan alert atas data yang sudah tersimpan.

Kanal email dan pesan instan hanya dicatat pada aturan. Pengiriman
sungguhan masuk tahap berikutnya agar MVP tidak mengirim pesan ke luar.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Alert, AlertRule, Mention
from app.services.clock import now_wib


def evaluate_rules(db: Session) -> int:
    now = now_wib()
    created = 0
    for rule in db.query(AlertRule).filter(AlertRule.is_active.is_(True)).all():
        title, message, issue_id = _check(db, rule, now)
        if not title:
            continue
        start = (now - timedelta(hours=12)).replace(minute=0, second=0, microsecond=0)
        exists = (
            db.query(Alert)
            .filter(Alert.rule_id == rule.id, Alert.title == title, Alert.triggered_at >= start)
            .first()
        )
        if exists:
            continue
        db.add(
            Alert(
                rule_id=rule.id,
                title=title,
                message=message,
                severity=rule.severity,
                triggered_at=now,
                is_read=False,
                issue_id=issue_id,
            )
        )
        created += 1
    db.commit()
    return created


def _check(db: Session, rule: AlertRule, now) -> tuple[str, str, int | None]:
    window_start = now - timedelta(hours=rule.window_hours)
    from app.services.blocklist import is_blocked, load_rules

    rules = load_rules(db)
    rows = [
        row
        for row in db.query(Mention).filter(Mention.published_at >= window_start).all()
        if not is_blocked(row.url, row.author_handle, row.author_name, row.source_name, row.title, rules)
    ]
    if rule.rule_type == "keyword_count":
        needle = (rule.keyword or "").casefold()
        hits = [row for row in rows if needle and needle in f"{row.title} {row.text}".casefold()]
        if len(hits) >= rule.threshold:
            return (
                f"Kata '{rule.keyword}' muncul {len(hits)} kali",
                f"Dalam {rule.window_hours} jam terakhir ada {len(hits)} mention yang memuat kata tersebut. Ambang aturan: {rule.threshold:.0f}.",
                hits[0].issue_id,
            )
    elif rule.rule_type == "tier1_downside":
        hits = [row for row in rows if row.source_tier == 1 and row.stance == "downside"]
        if len(hits) >= rule.threshold:
            return (
                "Media arus utama mengangkat konten downside",
                f"{len(hits)} mention tier-1 bernada downside dalam {rule.window_hours} jam.",
                hits[0].issue_id,
            )
    elif rule.rule_type == "kpw_negative":
        hits = [row for row in rows if row.is_kpw and row.sentiment == "negatif"]
        if len(hits) >= rule.threshold:
            return (
                "Mention negatif terkait KPw meningkat",
                f"{len(hits)} mention KPw bernada negatif dalam {rule.window_hours} jam.",
                hits[0].issue_id,
            )
    elif rule.rule_type == "negative_growth":
        prev_start = window_start - timedelta(hours=rule.window_hours)
        prev_rows = [
            row
            for row in db.query(Mention)
            .filter(Mention.published_at >= prev_start, Mention.published_at < window_start)
            .all()
            if not is_blocked(row.url, row.author_handle, row.author_name, row.source_name, row.title, rules)
        ]
        now_neg = sum(1 for row in rows if row.sentiment == "negatif")
        prev_neg = sum(1 for row in prev_rows if row.sentiment == "negatif")
        if prev_neg == 0 and now_neg >= rule.threshold:
            growth = 100.0
        elif prev_neg:
            growth = (now_neg - prev_neg) / prev_neg * 100
        else:
            growth = 0
        if growth >= rule.threshold and now_neg > 0:
            return (
                f"Mention negatif naik {growth:.0f}%",
                f"Dari {prev_neg} menjadi {now_neg} pada jendela {rule.window_hours} jam. Ambang: {rule.threshold:.0f}%.",
                None,
            )
    elif rule.rule_type == "volume_spike":
        if len(rows) >= 12:
            return (
                "Volume mention pada jendela aturan tergolong ramai",
                f"Ada {len(rows)} mention dalam {rule.window_hours} jam. Tinjau apakah ada isu tunggal di baliknya.",
                None,
            )
    return "", "", None
