"""Mengisi akun, kamus, dan aturan. Tidak membuat berita atau unggahan."""

from __future__ import annotations

import hashlib
import json
import random
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import (
    Alert,
    AlertRule,
    AppMeta,
    ChannelPost,
    Issue,
    Keyword,
    Mention,
    SavedQuery,
    User,
)
from app.nlp.risk import policy_relevance, policy_tags_for, score_risk
from app.seed_data import BRIEFS, CHANNELS, EXCLUSIONS, KEYWORD_GROUPS, SAVED_QUERIES, STORIES, USERS
from app.services.clock import now_wib
from app.services.matching import matched_terms

OUTLETS = [
    ("Detik", 1, 86),
    ("Kompas", 1, 90),
    ("CNBC Indonesia", 1, 84),
    ("Kontan", 1, 85),
    ("Bisnis.com", 1, 80),
    ("Bloomberg Technoz", 1, 88),
    ("CNN Indonesia", 1, 82),
    ("Tempo", 1, 86),
    ("Antara", 1, 90),
    ("Liputan6", 2, 74),
    ("Berita Jakarta", 2, 70),
    ("Warta Kota", 2, 68),
]

BASE_REACH = {
    "berita": 90000,
    "x": 35000,
    "instagram": 28000,
    "tiktok": 80000,
    "youtube": 32000,
    "facebook": 22000,
    "threads": 9000,
    "forum": 4000,
}

PLATFORM_SOURCE = {
    "x": "X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "facebook": "Facebook",
    "threads": "Threads",
    "forum": "Forum",
}


def seed_if_empty(db: Session) -> None:
    """Hanya akun, kamus, dan aturan. Tidak mengisi berita atau unggahan."""
    seed(db)


def seed(db: Session) -> None:
    if db.query(User).count() == 0:
        _users(db)
    if db.query(Keyword).count() == 0:
        _keywords(db)
        _queries(db)
    if db.query(AlertRule).count() == 0:
        _rules(db)
    from app.services.blocklist import ensure_defaults

    ensure_defaults(db)
    db.merge(AppMeta(key="data_mode", value="live"))
    db.commit()


def purge_mock(db: Session) -> int:
    """Hapus data karangan lama agar tidak tertampil bersama sumber nyata."""
    fake = db.query(Mention).filter(Mention.url.like("%contoh.media-monitor.local%")).count()
    mode = db.get(AppMeta, "data_mode")
    if fake == 0 and (mode is None or mode.value != "mock"):
        return 0
    removed = db.query(Mention).count()
    db.query(Mention).delete()
    db.query(Alert).delete()
    db.query(Issue).delete()
    db.query(ChannelPost).delete()
    db.merge(AppMeta(key="data_mode", value="live"))
    db.commit()
    return removed


def _users(db: Session) -> None:
    for username, full_name, role, password in USERS:
        db.add(
            User(
                username=username,
                full_name=full_name,
                role=role,
                password_hash=hash_password(password),
            )
        )


def _keywords(db: Session) -> list[Keyword]:
    rows = []
    for category, terms in KEYWORD_GROUPS.items():
        for term in terms:
            row = Keyword(term=term, category=category, mode="inklusi", is_active=True)
            db.add(row)
            rows.append(row)
    for term in EXCLUSIONS:
        row = Keyword(term=term, category="Eksklusi", mode="eksklusi", is_active=True)
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def _queries(db: Session) -> None:
    for name, expression in SAVED_QUERIES:
        db.add(SavedQuery(name=name, expression=expression, is_active=True))


def _rules(db: Session) -> dict[str, AlertRule]:
    specs = [
        ("Mention negatif naik tajam", "negative_growth", 40, 24, "kritis", ""),
        ("Kata sensitif hoaks muncul berulang", "keyword_count", 5, 48, "kritis", "hoaks"),
        ("Media arus utama mengangkat nada negatif", "tier1_downside", 2, 24, "waspada", ""),
        ("Mention negatif terkait KPw", "kpw_negative", 3, 72, "waspada", ""),
        ("Volume mention melonjak", "volume_spike", 2, 24, "info", ""),
    ]
    found = {}
    for name, rule_type, threshold, window, severity, keyword in specs:
        row = AlertRule(
            name=name,
            rule_type=rule_type,
            threshold=threshold,
            window_hours=window,
            severity=severity,
            keyword=keyword,
            channel="dashboard",
            is_active=True,
        )
        db.add(row)
        found[rule_type] = row
    db.flush()
    return found


def _issues(db: Session, now: datetime) -> dict[str, Issue]:
    found = {}
    for story in STORIES:
        started = now - timedelta(days=story["day_start"])
        row = Issue(
            code=story["code"],
            title=story["title"],
            summary=story["summary"],
            category=story["category"],
            stance=story["stance"],
            sentiment=story["sentiment"],
            risk_score=0,
            policy_relevance=0,
            spread_velocity=story["spread_velocity"],
            impact_level=story["impact_level"],
            status=story["status"],
            pic=story["pic"],
            started_at=started,
            ai_what=story["ai_what"],
            ai_who=story["ai_who"],
            ai_sentiment=story["ai_sentiment"],
            ai_impact=story["ai_impact"],
            ai_recommendation=story["ai_recommendation"],
            policy_tags="[]",
            is_critical=story["is_critical"],
            is_kpw=story["is_kpw"],
            spike_detected=story["spike_detected"],
        )
        db.add(row)
        found[story["code"]] = row
    db.flush()
    return found


def _mentions(db: Session, issues: dict[str, Issue], keywords: list[Keyword], now: datetime) -> None:
    outlet_cursor = 0
    for story in STORIES:
        issue = issues[story["code"]]
        bundle = [("berita", item) for item in story["news"]] + [("social", item) for item in story["social"]]
        locations = story.get("locations") or []
        for index, (kind, item) in enumerate(bundle):
            days_ago = _days_ago(story, index, len(bundle))
            published = _stamp(now, days_ago)
            if kind == "berita":
                title, text = item
                source, tier, credibility = OUTLETS[outlet_cursor % len(OUTLETS)]
                outlet_cursor += 1
                platform = "berita"
                author = f"Redaksi {source}"
                handle = source.lower().replace(" ", "").replace(".", "")
                needs_check = False
            else:
                platform, author, handle, text, needs_check = item
                title = text if len(text) <= 110 else text[:107] + "..."
                source = PLATFORM_SOURCE[platform]
                tier = 1 if handle == "@kpwbi_dki" else 3
                credibility = 90 if tier == 1 else (28 if needs_check else 48)
            location = locations[index % len(locations)] if locations else ""
            _add_mention(
                db,
                keywords,
                issue=issue,
                story=story,
                source=source,
                tier=tier,
                platform=platform,
                author=author,
                handle=handle,
                title=title,
                text=text,
                published=published,
                credibility=credibility,
                needs_check=needs_check,
                location=location,
                has_figure=story["has_public_figure"] and kind == "berita",
            )

    # Sebagian brief diletakkan di luar 30 hari terakhir agar perbandingan periode tidak kosong.
    for index, (title, text, sentiment, category) in enumerate(BRIEFS * 3):
        days_ago = 15 + index * 2
        stance = {"positif": "upside", "negatif": "downside", "netral": "netral"}[sentiment]
        published = _stamp(now, days_ago, hour=8 + (index % 8))
        source, tier, credibility = OUTLETS[index % len(OUTLETS)]
        _add_mention(
            db,
            keywords,
            issue=None,
            story={
                "stance": stance,
                "sentiment": sentiment,
                "category": category,
                "impact_level": "rendah",
                "spread_velocity": 22,
                "is_kpw": category in {"Kegiatan KPw DKI", "Ekonomi Jakarta"},
                "status": "baru",
                "pic": "",
                "has_public_figure": False,
            },
            source=source,
            tier=tier,
            platform="berita",
            author=f"Redaksi {source}",
            handle=source.lower().replace(" ", ""),
            title=title,
            text=text,
            published=published,
            credibility=credibility,
            needs_check=False,
            location="Jakarta Pusat" if category == "Ekonomi Jakarta" else "",
            has_figure=False,
        )


def _add_mention(db, keywords, **kwargs) -> None:
    story = kwargs["story"]
    text = kwargs["text"]
    title = kwargs["title"]
    full = f"{title}\n{text}"
    reach = _reach(kwargs["platform"], kwargs["tier"], story["spread_velocity"])
    likes = max(1, int(reach * random.uniform(0.008, 0.04)))
    shares = max(0, int(likes * random.uniform(0.15, 0.7)))
    comments = max(0, int(likes * random.uniform(0.05, 0.3)))
    tags = policy_tags_for(full)
    relevance = policy_relevance(full, story["category"])
    risk = score_risk(
        sentiment=story["sentiment"],
        stance=story["stance"],
        reach=reach,
        source_tier=kwargs["tier"],
        velocity=story["spread_velocity"],
        has_public_figure=kwargs["has_figure"],
        credibility=kwargs["credibility"],
    )
    score = {"positif": 0.62, "netral": 0.02, "negatif": -0.64}[story["sentiment"]]
    note = ""
    if kwargs["needs_check"]:
        note = (
            "Pola unggahan mirip dengan akun lain dan ajakannya mendesak. "
            "Ini indikasi awal, bukan kesimpulan bahwa akun adalah bot. Perlu diverifikasi."
        )
    identity = f"{kwargs['platform']}|{title}|{kwargs['handle']}"
    db.add(
        Mention(
            content_hash=hashlib.sha256(identity.encode()).hexdigest(),
            source_name=kwargs["source"],
            source_tier=kwargs["tier"],
            platform=kwargs["platform"],
            url=_url(kwargs["platform"], title),
            author_name=kwargs["author"],
            author_handle=kwargs["handle"],
            published_at=kwargs["published"],
            title=title,
            text=text,
            likes=likes,
            shares=shares,
            comments=comments,
            reach_estimate=reach,
            keyword_matches=json.dumps(matched_terms(full, keywords), ensure_ascii=False),
            sentiment=story["sentiment"],
            sentiment_score=score,
            stance=story["stance"],
            confidence=0.55 if kwargs["needs_check"] else 0.81,
            rationale=_rationale(story["stance"], story["sentiment"], story["category"], tags),
            category=story["category"],
            risk_score=risk,
            policy_relevance=round(relevance, 1),
            policy_tags=json.dumps(tags, ensure_ascii=False),
            spread_velocity=story["spread_velocity"],
            impact_level=story["impact_level"],
            credibility=kwargs["credibility"],
            has_public_figure=kwargs["has_figure"],
            needs_verification=kwargs["needs_check"],
            verification_note=note,
            is_kpw=story["is_kpw"] or "kpw" in full.casefold(),
            location=kwargs["location"],
            status=story["status"] if kwargs["platform"] == "berita" else "baru",
            pic=story["pic"] if kwargs["platform"] == "berita" else "",
            issue_id=None if kwargs["issue"] is None else kwargs["issue"].id,
        )
    )


def _refresh_issue_scores(db: Session, issues: dict[str, Issue]) -> None:
    for issue in issues.values():
        rows = db.query(Mention).filter(Mention.issue_id == issue.id).all()
        if not rows:
            continue
        issue.risk_score = round(sum(row.risk_score for row in rows) / len(rows), 1)
        issue.policy_relevance = round(max(row.policy_relevance for row in rows), 1)
        tags: list[str] = []
        for row in rows:
            for tag in json.loads(row.policy_tags):
                if tag not in tags:
                    tags.append(tag)
        issue.policy_tags = json.dumps(tags, ensure_ascii=False)
        issue.started_at = min(row.published_at for row in rows)
        if issue.risk_score >= 75 and issue.stance == "downside":
            issue.is_critical = True


def _channels(db: Session, now: datetime) -> None:
    for platform, title, days_ago, reach, likes, comments, shares in CHANNELS:
        engagement = round((likes + comments + shares) / reach * 100, 2) if reach else 0
        db.add(
            ChannelPost(
                platform=platform,
                title=title,
                published_at=_stamp(now, days_ago, hour=10),
                reach=reach,
                likes=likes,
                comments=comments,
                shares=shares,
                engagement_rate=engagement,
            )
        )


def _alerts(db: Session, rules: dict[str, AlertRule], issues: dict[str, Issue], now: datetime) -> None:
    rows = [
        (
            "keyword_count",
            "kritis",
            "Lonjakan hoaks mengatasnamakan Bank Indonesia",
            "Kata 'hoaks' muncul berulang dalam 48 jam terakhir dan sudah diangkat media arus utama. Periksa isu terkait sebelum menyusun klarifikasi.",
            "ISS-HOAX",
            now - timedelta(hours=2),
            False,
        ),
        (
            "tier1_downside",
            "waspada",
            "Media arus utama menyorot pelemahan rupiah",
            "Lebih dari satu media tier-1 memuat nada negatif pada nilai tukar. Siapkan kalimat jangkar, jangan mengutip angka operasi.",
            "ISS-RUPIAH",
            now - timedelta(hours=5),
            False,
        ),
        (
            "negative_growth",
            "info",
            "Percakapan UMKM dan QRIS bergerak naik",
            "Volume mention kegiatan KPw meningkat, dengan nada yang masih positif. Cocok dipantau sebagai ukuran kampanye, bukan sebagai krisis.",
            "ISS-UMKM",
            now - timedelta(days=1),
            True,
        ),
        (
            "kpw_negative",
            "waspada",
            "Sisa percakapan gangguan BI-FAST masih dipantau",
            "Layanan dilaporkan pulih. Alert ini ditandai sudah dibaca dan tetap disimpan sebagai jejak.",
            "ISS-BIFAST",
            now - timedelta(days=5),
            True,
        ),
    ]
    for rule_type, severity, title, message, code, when, read in rows:
        db.add(
            Alert(
                rule_id=rules[rule_type].id,
                title=title,
                message=message,
                severity=severity,
                triggered_at=when,
                is_read=read,
                issue_id=issues[code].id,
            )
        )


def _days_ago(story: dict, index: int, count: int) -> int:
    start = story["day_start"]
    end = story["day_end"]
    if count <= 1 or start == end:
        return end
    step = (start - end) / (count - 1)
    return int(round(start - index * step))


def _stamp(now: datetime, days_ago: int, hour: int | None = None) -> datetime:
    day = (now - timedelta(days=days_ago)).date()
    if hour is None:
        if days_ago == 0:
            hour = random.randint(6, max(6, now.hour))
        else:
            hour = random.randint(7, 20)
    minute = random.randint(0, 59)
    stamp = datetime(day.year, day.month, day.day, hour, minute)
    if stamp > now:
        stamp = now - timedelta(minutes=random.randint(5, 40))
    return stamp


def _reach(platform: str, tier: int, velocity: float) -> int:
    tier_mul = {1: 2.3, 2: 1.15, 3: 0.62}[tier]
    heat = 0.75 + velocity / 140
    return int(BASE_REACH[platform] * tier_mul * heat * random.uniform(0.75, 1.25))


def _url(platform: str, title: str) -> str:
    raise RuntimeError("URL contoh tidak boleh dibuat.")


def _rationale(stance: str, sentiment: str, category: str, tags: list[str]) -> str:
    tone = {
        "upside": "nada peluang, apresiasi, atau kegiatan yang membangun kepercayaan",
        "downside": "nada risiko, kritik, gangguan, atau potensi kerugian reputasi",
        "netral": "laporan yang relatif berimbang tanpa dorongan sikap yang kuat",
    }[stance]
    label = {"upside": "Upside", "downside": "Downside", "netral": "Netral"}[stance]
    extra = f" Kebijakan yang tersentuh: {', '.join(tags)}." if tags else ""
    return (
        f"Diklasifikasikan {label} ({sentiment}) karena teks menunjukkan {tone}. "
        f"Subkategori: {category}.{extra}"
    )
