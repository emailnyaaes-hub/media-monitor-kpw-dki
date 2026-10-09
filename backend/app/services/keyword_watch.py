"""Pantauan kata valuta, regulasi pembayaran, dan dompet digital.

Angka dihitung dari mention yang sudah tersimpan. Kurs tidak diisi.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Keyword, Mention, SavedQuery
from app.nlp.boolean import term_in_text
from app.services.analytics import STOPWORDS, _delta_pct, _sentiment_share, _tokens, base_query, previous_window

WATCH_GROUPS = {
    "Valuta asing": ["money changer", "dolar", "kupva BB", "tukar rupiah"],
    "Regulasi/Industri": ["PJP", "penyelenggara sistem pembayaran"],
    "Dompet digital/Fintech": ["flip", "GoPay", "DANA", "OVO"],
}

COLORS = {
    "Valuta asing": "#0B1F3A",
    "Regulasi/Industri": "#1E4A7A",
    "Dompet digital/Fintech": "#8A5A00",
}

QUERY_NAME = "Paket valuta dan pembayaran"
QUERY_EXPRESSION = (
    '("money changer" OR dolar OR "kupva BB" OR "tukar rupiah" OR PJP OR '
    '"penyelenggara sistem pembayaran" OR flip OR GoPay OR DANA OR OVO) '
    "AND NOT (lowongan OR karir OR loker)"
)

MARKERS = ("penipuan", "ilegal", "error", "gangguan", "sanksi")
WEEKDAYS = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
SOURCE_GROUP = {
    "berita": "Berita online",
    "x": "Media sosial",
    "instagram": "Media sosial",
    "tiktok": "Media sosial",
    "youtube": "Media sosial",
    "facebook": "Media sosial",
    "threads": "Media sosial",
    "forum": "Forum",
}


def ensure_watch_keywords(db: Session) -> bool:
    added = False
    for category, terms in WATCH_GROUPS.items():
        for term in terms:
            exists = (
                db.query(Keyword)
                .filter(Keyword.term == term, Keyword.mode == "inklusi")
                .first()
            )
            if exists:
                continue
            db.add(Keyword(term=term, category=category, mode="inklusi", is_active=True))
            added = True
    if db.query(SavedQuery).filter(SavedQuery.name == QUERY_NAME).first() is None:
        db.add(SavedQuery(name=QUERY_NAME, expression=QUERY_EXPRESSION, is_active=True))
        added = True
    if added:
        db.commit()
    return added


def catalog(db: Session) -> list[dict]:
    rows = (
        db.query(Keyword)
        .filter(Keyword.mode == "inklusi", Keyword.category.in_(list(WATCH_GROUPS)))
        .order_by(Keyword.category, Keyword.term)
        .all()
    )
    return [
        {
            "id": row.id,
            "term": row.term,
            "category": row.category,
            "color": COLORS.get(row.category, "#5C6570"),
            "is_active": row.is_active,
        }
        for row in rows
    ]


def snapshot(db: Session, window: dict, terms: list[str], grain: str) -> dict:
    chosen = _chosen(db, terms)
    current = _matched(base_query(db, window).all(), chosen)
    previous_rows = _matched(base_query(db, previous_window(window)).all(), chosen)
    share = _sentiment_share(current)
    counts = _counts(current, chosen)
    top = max(counts, key=lambda item: item["count"]) if counts else None
    if top and top["count"] == 0:
        top = None
    return {
        "catalog": catalog(db),
        "keywords": chosen,
        "kpis": {
            "total": len(current),
            "previous": len(previous_rows),
            "delta": len(current) - len(previous_rows),
            "delta_pct": _delta_pct(len(current), len(previous_rows)),
            "top_keyword": top,
            "sentiment_pct": share,
        },
        "trend": _trend(current, chosen, window, grain),
        "volumes": counts,
        "sources": _sources(current),
        "cowords": _cowords(current, chosen),
        "heatmap": _heatmap(current),
        "alerts": _alerts(current, window),
        "fx": {
            "available": False,
            "note": "Grafik tren kurs USD/IDR: [data perlu dilengkapi]. Seri kurs resmi belum terhubung.",
        },
    }


def _chosen(db: Session, terms: list[str]) -> list[dict]:
    rows = [item for item in catalog(db) if item["is_active"]]
    wanted = {term.casefold() for term in terms if term.strip()}
    if wanted:
        rows = [item for item in rows if item["term"].casefold() in wanted]
    return rows


def _matched(rows: list[Mention], keywords: list[dict]) -> list[Mention]:
    if not keywords:
        return []
    kept = []
    for row in rows:
        blob = f"{row.title}\n{row.text}"
        if any(term_in_text(item["term"], blob) for item in keywords):
            kept.append(row)
    return kept


def _counts(rows: list[Mention], keywords: list[dict]) -> list[dict]:
    output = []
    for item in keywords:
        count = sum(1 for row in rows if term_in_text(item["term"], f"{row.title}\n{row.text}"))
        output.append({**item, "count": count})
    output.sort(key=lambda item: item["count"], reverse=True)
    return output


def _trend(rows: list[Mention], keywords: list[dict], window: dict, grain: str) -> dict:
    buckets = _buckets(window, grain)
    series = {item["term"]: {bucket: 0 for bucket in buckets} for item in keywords}
    for row in rows:
        bucket = _bucket(row.published_at, grain)
        if bucket not in buckets:
            continue
        blob = f"{row.title}\n{row.text}"
        for item in keywords:
            if term_in_text(item["term"], blob):
                series[item["term"]][bucket] += 1
    points = []
    for bucket in buckets:
        point = {"date": bucket}
        for item in keywords:
            point[item["term"]] = series[item["term"]][bucket]
        points.append(point)
    return {"grain": grain, "series": keywords, "points": points}


def _buckets(window: dict, grain: str) -> list[str]:
    start = window["date_from"]
    end = window["date_to"]
    found = []
    seen = set()
    day = start
    while day <= end:
        label = _bucket(datetime.combine(day, datetime.min.time()), grain)
        if label not in seen:
            seen.add(label)
            found.append(label)
        day += timedelta(days=1)
    return found


def _bucket(moment: datetime, grain: str) -> str:
    if grain == "month":
        return f"{moment.year:04d}-{moment.month:02d}-01"
    if grain == "week":
        start = moment.date() - timedelta(days=moment.weekday())
        return start.isoformat()
    return moment.date().isoformat()


def _sources(rows: list[Mention]) -> list[dict]:
    counts: Counter[str] = Counter()
    ids: dict[str, str] = {}
    for row in rows:
        label = SOURCE_GROUP.get(row.platform, "Lainnya")
        counts[label] += 1
        ids.setdefault(label, row.platform if label not in {"Media sosial", "Lainnya"} else "")
    return [{"name": name, "count": count, "platform": ids.get(name, "")} for name, count in counts.most_common()]


def _cowords(rows: list[Mention], keywords: list[dict]) -> list[dict]:
    banned = {item["term"].casefold() for item in keywords}
    banned.update(part for item in keywords for part in item["term"].casefold().split())
    words: Counter[str] = Counter()
    for row in rows:
        words.update(_tokens(f"{row.title} {row.text}"))
    output = []
    for word, count in words.most_common(40):
        if word in banned or word in STOPWORDS:
            continue
        output.append({"text": word, "value": count})
        if len(output) == 24:
            break
    return output


def _heatmap(rows: list[Mention]) -> dict:
    grid = [[0 for _ in range(24)] for _ in WEEKDAYS]
    for row in rows:
        grid[row.published_at.weekday()][row.published_at.hour] += 1
    return {"days": list(WEEKDAYS), "hours": list(range(24)), "cells": grid}


def _alerts(rows: list[Mention], window: dict) -> list[dict]:
    notes = []
    by_day: dict[str, int] = defaultdict(int)
    day = window["date_from"]
    while day <= window["date_to"]:
        by_day[day.isoformat()] = 0
        day += timedelta(days=1)
    for row in rows:
        by_day[row.published_at.date().isoformat()] += 1
    ordered = [by_day[key] for key in sorted(by_day)]
    if len(ordered) >= 5:
        average = sum(ordered) / len(ordered)
        last = ordered[-1]
        if average > 0 and last >= average * 2:
            notes.append(
                {
                    "kind": "lonjakan",
                    "title": f"Hari terakhir {last} mention, sedikitnya dua kali rata-rata harian {average:.1f}".replace(".", ","),
                    "detail": "Ambang tampilan: lebih dari 2 kali rata-rata harian pada rentang ini.",
                }
            )
    for marker in MARKERS:
        hits = [row for row in rows if term_in_text(marker, f"{row.title}\n{row.text}")]
        if not hits:
            continue
        sample = hits[0]
        notes.append(
            {
                "kind": "penanda",
                "title": f"Kata '{marker}' muncul pada {len(hits)} mention",
                "detail": sample.title,
                "marker": marker,
            }
        )
    if not notes:
        notes.append(
            {
                "kind": "tenang",
                "title": "Tidak ada lonjakan atau penanda negatif pada rentang ini",
                "detail": "Penanda yang dicek: penipuan, ilegal, error, gangguan, sanksi.",
            }
        )
    return notes
