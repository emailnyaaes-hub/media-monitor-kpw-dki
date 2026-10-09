"""Agregat untuk halaman dashboard. Filter tanggal berlaku di semua fungsi baca."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.constants import IMPACT_SCORE, JAKARTA_AREAS
from app.models import ChannelPost, Issue, Mention
from app.nlp.boolean import term_in_text
from app.services.serialize import issue_card, loads, mention_card, quadrant

STOPWORDS = {
    "yang", "dan", "dari", "untuk", "pada", "dengan", "ini", "itu", "ada", "akan",
    "juga", "atau", "serta", "para", "telah", "dapat", "lebih", "sudah", "karena",
    "oleh", "atas", "adalah", "sebagai", "dalam", "tidak", "bukan", "secara",
    "kepada", "bahwa", "jika", "maka", "saja", "masih", "sangat", "tentang",
    "mereka", "kami", "kita", "anda", "hari", "tahun", "persen", "juta", "agar",
    "saat", "bagi", "baru", "baru", "bisa", "kalau", "sudah", "hanya", "setelah",
    "sebelum", "antara", "tanpa", "melalui", "terhadap", "sebuah", "salah",
    "satu", "dua", "tiga", "jadi", "nya", "kah", "pun", "lah", "the", "and",
    "bank", "indonesia", "jakarta", "warga", "media", "hari", "ini", "yang",
}

ENTITIES = [
    "Gubernur BI",
    "Deputi Gubernur BI",
    "KPw BI DKI Jakarta",
    "KPw BI DKI",
    "TPID DKI",
    "Bank Indonesia",
    "Rapat Dewan Gubernur",
    "UMKM",
]


def parse_window(
    date_from: date | None,
    date_to: date | None,
    platform: str | None,
    category: str | None,
    location: str | None = None,
) -> dict:
    today = date.today()
    end_date = date_to or today
    start_date = date_from or (end_date - timedelta(days=29))
    if start_date > end_date:
        raise ValueError("Tanggal mulai lebih besar dari tanggal akhir")
    return {
        "date_from": start_date,
        "date_to": end_date,
        "start": datetime.combine(start_date, time.min),
        "end": datetime.combine(end_date, time.max),
        "platform": None if not platform or platform == "semua" else platform,
        "category": None if not category or category == "semua" else category,
        "location": None if not location or location == "semua" else location,
    }


def previous_window(window: dict) -> dict:
    length = (window["date_to"] - window["date_from"]).days + 1
    end_date = window["date_from"] - timedelta(days=1)
    start_date = end_date - timedelta(days=length - 1)
    return {
        **window,
        "date_from": start_date,
        "date_to": end_date,
        "start": datetime.combine(start_date, time.min),
        "end": datetime.combine(end_date, time.max),
    }


def apply_filters(query: Query, window: dict, model=Mention) -> Query:
    column = model.published_at
    query = query.filter(column >= window["start"], column <= window["end"])
    if window.get("platform") and hasattr(model, "platform"):
        query = query.filter(model.platform == window["platform"])
    if window.get("category") and hasattr(model, "category"):
        query = query.filter(model.category == window["category"])
    if window.get("location") and hasattr(model, "location"):
        query = query.filter(model.location == window["location"])
    return query


def base_query(db: Session, window: dict) -> Query:
    from app.services.blocklist import external_only, load_rules

    return external_only(apply_filters(db.query(Mention), window), load_rules(db))


def _delta_pct(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return round((current - previous) / abs(previous) * 100, 1)


def _sentiment_share(rows: list[Mention]) -> dict[str, float]:
    total = len(rows) or 1
    counts = Counter(row.sentiment for row in rows)
    return {name: round(counts.get(name, 0) / total * 100, 1) for name in ("positif", "netral", "negatif")}


def _net(share: dict[str, float]) -> float:
    return round(share["positif"] - share["negatif"], 1)


def category_shift(db: Session, window: dict) -> list[dict]:
    """Selisih jumlah mention per kategori terhadap jendela sebelumnya."""

    def counts(target: dict) -> Counter:
        return Counter(row.category or "Lainnya" for row in base_query(db, target).all())

    current = counts(window)
    previous = counts(previous_window(window))
    names = set(current) | set(previous)
    rows = [
        {
            "category": name,
            "current": current[name],
            "previous": previous[name],
            "delta": current[name] - previous[name],
        }
        for name in names
    ]
    rows.sort(key=lambda item: abs(item["delta"]), reverse=True)
    return rows


def area_counts(db: Session, window: dict) -> list[dict]:
    """Jumlah mention yang menyebut kota administrasi. Bukan agregat BPS."""
    grouped: dict[str, list[Mention]] = defaultdict(list)
    for row in base_query(db, window).all():
        if row.location in JAKARTA_AREAS:
            grouped[row.location].append(row)
    output = []
    for name in JAKARTA_AREAS:
        items = grouped.get(name, [])
        share = _sentiment_share(items) if items else None
        output.append(
            {
                "name": name,
                "count": len(items),
                "negatif": share["negatif"] if share else None,
            }
        )
    return output


def overview(db: Session, window: dict) -> dict:
    current_rows = base_query(db, window).all()
    previous = previous_window(window)
    previous_rows = base_query(db, previous).all()
    share = _sentiment_share(current_rows)
    prev_share = _sentiment_share(previous_rows)
    reach = sum(row.reach_estimate for row in current_rows)
    prev_reach = sum(row.reach_estimate for row in previous_rows)
    critical_now = _critical_count(db, window)
    critical_prev = _critical_count(db, previous)
    net = _net(share)
    prev_net = _net(prev_share)
    return {
        "period": {"from": window["date_from"].isoformat(), "to": window["date_to"].isoformat()},
        "previous_period": {
            "from": previous["date_from"].isoformat(),
            "to": previous["date_to"].isoformat(),
        },
        "kpis": {
            "total_mention": {
                "value": len(current_rows),
                "previous": len(previous_rows),
                "delta_pct": _delta_pct(len(current_rows), len(previous_rows)),
            },
            "sentiment_pct": {**share, "previous": prev_share},
            "net_sentiment": {
                "value": net,
                "previous": prev_net,
                "delta_points": round(net - prev_net, 1),
            },
            "reach": {
                "value": reach,
                "previous": prev_reach,
                "delta_pct": _delta_pct(reach, prev_reach),
            },
            "critical_issues": {
                "value": critical_now,
                "previous": critical_prev,
                "delta_pct": _delta_pct(critical_now, critical_prev),
            },
        },
        "trend": trend(db, window, "day"),
        "top_upside": _top_stance(db, window, "upside"),
        "top_downside": _top_stance(db, window, "downside"),
        "critical_issue_list": _critical_issues(db, window),
        "category_shift": category_shift(db, window),
        "areas": area_counts(db, window),
    }


def _critical_count(db: Session, window: dict) -> int:
    ids = {
        row.issue_id
        for row in base_query(db, window).filter(Mention.issue_id.isnot(None)).all()
        if row.issue_id
    }
    if not ids:
        return 0
    return (
        db.query(Issue)
        .filter(Issue.id.in_(ids), Issue.is_critical.is_(True), Issue.status != "selesai")
        .count()
    )


def _critical_issues(db: Session, window: dict) -> list[dict]:
    cards = []
    for issue, count, last_at in _issue_rows(db, window):
        if issue.is_critical and issue.status != "selesai":
            cards.append(issue_card(issue, count, last_at.isoformat(timespec="minutes") if last_at else None))
    return cards


def _top_stance(db: Session, window: dict, stance: str) -> dict:
    """Utamakan hari terakhir pada rentang. Bila sepi, lebarkan ke tiga hari."""
    last_day = window["date_to"]
    narrow = {
        **window,
        "date_from": last_day,
        "start": datetime.combine(last_day, time.min),
    }
    rows = (
        base_query(db, narrow)
        .filter(Mention.stance == stance)
        .order_by(Mention.reach_estimate.desc())
        .limit(5)
        .all()
    )
    label = "hari terakhir pada rentang"
    if len(rows) < 2:
        start_day = last_day - timedelta(days=2)
        wider = {
            **window,
            "date_from": max(start_day, window["date_from"]),
            "start": datetime.combine(max(start_day, window["date_from"]), time.min),
        }
        rows = (
            base_query(db, wider)
            .filter(Mention.stance == stance)
            .order_by(Mention.reach_estimate.desc())
            .limit(5)
            .all()
        )
        label = "3 hari terakhir pada rentang"
    return {"window_label": label, "items": [mention_card(row) for row in rows]}


def trend(db: Session, window: dict, granularity: str) -> list[dict]:
    rows = base_query(db, window).all()
    buckets: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        buckets[_bucket(row.published_at, granularity)][row.sentiment] += 1
    points = []
    for key in sorted(buckets):
        counts = buckets[key]
        total = sum(counts.values())
        points.append(
            {
                "date": key,
                "positif": counts.get("positif", 0),
                "netral": counts.get("netral", 0),
                "negatif": counts.get("negatif", 0),
                "total": total,
                "spike": False,
            }
        )
    _mark_spikes(points)
    return points


def _bucket(moment: datetime, granularity: str) -> str:
    if granularity == "month":
        return moment.strftime("%Y-%m")
    if granularity == "week":
        start = moment.date() - timedelta(days=moment.weekday())
        return start.isoformat()
    return moment.date().isoformat()


def _mark_spikes(points: list[dict]) -> None:
    totals = [point["total"] for point in points]
    if len(totals) < 5:
        return
    mean = sum(totals) / len(totals)
    variance = sum((value - mean) ** 2 for value in totals) / len(totals)
    std = math.sqrt(variance)
    if std == 0:
        return
    for point in points:
        point["spike"] = point["total"] >= mean + 2 * std and point["total"] >= 8


def _issue_rows(db: Session, window: dict):
    mention_q = base_query(db, window).filter(Mention.issue_id.isnot(None))
    grouped = (
        mention_q.with_entities(
            Mention.issue_id,
            func.count(Mention.id),
            func.max(Mention.published_at),
        )
        .group_by(Mention.issue_id)
        .all()
    )
    if not grouped:
        return []
    ids = [row[0] for row in grouped]
    issues = {row.id: row for row in db.query(Issue).filter(Issue.id.in_(ids)).all()}
    output = []
    for issue_id, count, last_at in grouped:
        issue = issues.get(issue_id)
        if issue is None:
            continue
        if window.get("category") and issue.category != window["category"]:
            continue
        output.append((issue, count, last_at))
    output.sort(key=lambda item: item[0].risk_score, reverse=True)
    return output


def list_issues(db: Session, window: dict, kpw_only: bool = False) -> list[dict]:
    cards = []
    for issue, count, last_at in _issue_rows(db, window):
        if kpw_only and not issue.is_kpw:
            continue
        cards.append(issue_card(issue, count, last_at.isoformat(timespec="minutes") if last_at else None))
    return cards


def topics(db: Session, window: dict) -> dict:
    rows = base_query(db, window).all()
    words: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    for row in rows:
        words.update(_tokens(f"{row.title} {row.text}"))
        tags.update(re.findall(r"#(\w+)", f"{row.title} {row.text}", flags=re.UNICODE))
    entities = []
    for name in ENTITIES:
        count = sum(1 for row in rows if name.casefold() in f"{row.title} {row.text}".casefold())
        if count:
            entities.append({"name": name, "count": count})
    entities.sort(key=lambda item: item["count"], reverse=True)
    return {
        "words": [{"text": word, "value": count} for word, count in words.most_common(40)],
        "hashtags": [{"tag": tag, "count": count} for tag, count in tags.most_common(12)],
        "entities": entities,
        "method_note": (
            "Pada MVP, klaster isu disusun manual dari kelompok mention. "
            "Topic modeling otomatis menyusul pada tahap berikutnya."
        ),
    }


def related_words(db: Session, window: dict, term: str) -> list[dict]:
    needle = term.casefold().lstrip("#")
    rows = [
        row
        for row in base_query(db, window).all()
        if needle in f"{row.title} {row.text}".casefold()
    ]
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(_tokens(f"{row.title} {row.text}"))
    counts.pop(needle, None)
    return [{"text": word, "value": count} for word, count in counts.most_common(12)]


def _tokens(text: str) -> list[str]:
    found = re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", text.casefold())
    return [token for token in found if token not in STOPWORDS and not token.startswith("http")]


def radar(db: Session, window: dict) -> list[dict]:
    cards = list_issues(db, window)
    for card in cards:
        card["x"] = card["spread_velocity"]
        card["y"] = card["impact_score"]
    return cards


def policy_feedback(db: Session, window: dict) -> list[dict]:
    rows = base_query(db, window).all()
    grouped: dict[str, list[Mention]] = defaultdict(list)
    for row in rows:
        for tag in loads(row.policy_tags):
            grouped[tag].append(row)
    report = []
    for tag, items in grouped.items():
        share = _sentiment_share(items)
        aspirations = [{"title": row.title, "url": row.url} for row in items if row.stance == "upside"][:3]
        criticisms = [{"title": row.title, "url": row.url} for row in items if row.stance == "downside"][:3]
        report.append(
            {
                "policy": tag,
                "mentions": len(items),
                "positif": share["positif"],
                "netral": share["netral"],
                "negatif": share["negatif"],
                "aspirations": aspirations,
                "criticisms": criticisms,
                "relevance_avg": round(sum(row.policy_relevance for row in items) / len(items), 1),
            }
        )
    report.sort(key=lambda item: item["mentions"], reverse=True)
    return report


def kpw_overview(db: Session, window: dict) -> dict:
    rows = base_query(db, window).filter(Mention.is_kpw.is_(True)).all()
    share = _sentiment_share(rows)
    areas: Counter[str] = Counter(row.location for row in rows if row.location)
    return {
        "kpis": {
            "total_mention": len(rows),
            "net_sentiment": _net(share),
            "reach": sum(row.reach_estimate for row in rows),
            "sentiment_pct": share,
        },
        "areas": [{"name": name, "count": count} for name, count in areas.most_common()],
        "issues": [card for card in list_issues(db, window, kpw_only=True)],
        "map_note": "Peta ini skematik berdasarkan kota administrasi yang ditandai pada data, bukan peta GIS.",
    }


def channels(db: Session, window: dict) -> dict:
    rows = apply_filters(db.query(ChannelPost), window, ChannelPost).all()
    by_platform: dict[str, dict] = {}
    for row in rows:
        bucket = by_platform.setdefault(
            row.platform, {"platform": row.platform, "posts": 0, "reach": 0, "engagement_rate": 0.0}
        )
        bucket["posts"] += 1
        bucket["reach"] += row.reach
        bucket["engagement_rate"] += row.engagement_rate
    summary = []
    for bucket in by_platform.values():
        bucket["engagement_rate"] = round(bucket["engagement_rate"] / bucket["posts"], 2)
        summary.append(bucket)
    posts = [
        {
            "id": row.id,
            "platform": row.platform,
            "title": row.title,
            "published_at": row.published_at.isoformat(timespec="minutes"),
            "reach": row.reach,
            "likes": row.likes,
            "comments": row.comments,
            "shares": row.shares,
            "engagement_rate": row.engagement_rate,
        }
        for row in sorted(rows, key=lambda item: item.engagement_rate, reverse=True)
    ]
    note = ""
    status = "berhasil"
    if not posts:
        status = "tidak_tersedia"
        note = "Sumber tidak tersedia. Metrik kanal resmi butuh YouTube Data API atau Meta Graph API dan belum dikonfigurasi."
    return {"summary": summary, "posts": posts, "status": status, "message": note}


def media_ranking(db: Session, window: dict) -> list[dict]:
    rows = base_query(db, window).filter(Mention.platform == "berita").all()
    grouped: dict[str, list[Mention]] = defaultdict(list)
    for row in rows:
        grouped[row.source_name].append(row)
    ranking = []
    for name, items in grouped.items():
        share = _sentiment_share(items)
        if share["positif"] >= share["negatif"] + 15:
            tilt = "cenderung positif"
        elif share["negatif"] >= share["positif"] + 15:
            tilt = "cenderung negatif"
        else:
            tilt = "seimbang"
        ranking.append(
            {
                "name": name,
                "tier": min(item.source_tier for item in items),
                "mentions": len(items),
                "reach": sum(item.reach_estimate for item in items),
                "positif": share["positif"],
                "negatif": share["negatif"],
                "tilt": tilt,
            }
        )
    ranking.sort(key=lambda item: item["reach"], reverse=True)
    return ranking


def influencers(db: Session, window: dict) -> list[dict]:
    rows = base_query(db, window).filter(Mention.platform != "berita").all()
    grouped: dict[str, list[Mention]] = defaultdict(list)
    for row in rows:
        grouped[row.author_handle or row.author_name].append(row)
    ranking = []
    for handle, items in grouped.items():
        share = _sentiment_share(items)
        flagged = any(item.needs_verification for item in items)
        note = next((item.verification_note for item in items if item.verification_note), "")
        ranking.append(
            {
                "handle": handle,
                "name": items[0].author_name,
                "platform": items[0].platform,
                "mentions": len(items),
                "reach": sum(item.reach_estimate for item in items),
                "negatif": share["negatif"],
                "positif": share["positif"],
                "needs_verification": flagged,
                "verification_note": note,
            }
        )
    ranking.sort(key=lambda item: (item["needs_verification"], item["reach"]), reverse=True)
    return ranking


def category_breakdown(db: Session, window: dict) -> list[dict]:
    rows = base_query(db, window).all()
    grouped: dict[str, list[Mention]] = defaultdict(list)
    for row in rows:
        grouped[row.category].append(row)
    output = []
    for name, items in grouped.items():
        share = _sentiment_share(items)
        output.append(
            {
                "category": name,
                "total": len(items),
                "positif": sum(1 for item in items if item.sentiment == "positif"),
                "netral": sum(1 for item in items if item.sentiment == "netral"),
                "negatif": sum(1 for item in items if item.sentiment == "negatif"),
                "net_sentiment": _net(share),
            }
        )
    output.sort(key=lambda item: item["total"], reverse=True)
    return output


def search_mentions(db: Session, window: dict, params: dict) -> dict:
    query = base_query(db, window)
    if params.get("sentiment"):
        query = query.filter(Mention.sentiment == params["sentiment"])
    if params.get("stance"):
        query = query.filter(Mention.stance == params["stance"])
    if params.get("status"):
        query = query.filter(Mention.status == params["status"])
    if params.get("source"):
        query = query.filter(Mention.source_name == params["source"])
    if params.get("min_risk") is not None:
        query = query.filter(Mention.risk_score >= params["min_risk"])
    if params.get("issue_id"):
        query = query.filter(Mention.issue_id == params["issue_id"])
    if params.get("kpw"):
        query = query.filter(Mention.is_kpw.is_(True))
    rows = query.all()
    needle = (params.get("q") or "").casefold().strip()
    keyword = (params.get("keyword") or "").casefold().strip()
    terms = [part.strip() for part in str(params.get("keywords") or "").split(",") if part.strip()]
    filtered = []
    for row in rows:
        blob = f"{row.title}\n{row.text}"
        folded = f"{blob} {row.author_name} {row.source_name}".casefold()
        if needle and needle not in folded:
            continue
        if keyword and keyword not in row.keyword_matches.casefold() and keyword not in folded:
            continue
        if terms and not any(term_in_text(term, blob) for term in terms):
            continue
        if params.get("weekday") not in (None, "") and row.published_at.weekday() != int(params["weekday"]):
            continue
        if params.get("hour") not in (None, "") and row.published_at.hour != int(params["hour"]):
            continue
        filtered.append(row)
    sort = params.get("sort") or "terbaru"
    if sort == "risiko":
        filtered.sort(key=lambda row: row.risk_score, reverse=True)
    elif sort == "jangkauan":
        filtered.sort(key=lambda row: row.reach_estimate, reverse=True)
    else:
        filtered.sort(key=lambda row: row.published_at, reverse=True)
    page = max(1, int(params.get("page") or 1))
    page_size = min(100, max(1, int(params.get("page_size") or 20)))
    start = (page - 1) * page_size
    return {
        "total": len(filtered),
        "page": page,
        "page_size": page_size,
        "items": [mention_card(row) for row in filtered[start : start + page_size]],
    }
