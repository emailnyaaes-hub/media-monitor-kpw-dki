"""Mengubah teks dan angka basis data menjadi JSON yang stabil untuk UI."""

from __future__ import annotations

import json

from app.constants import IMPACT_SCORE
from app.models import Alert, Issue, Mention


def loads(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def quadrant(impact_level: str, velocity: float) -> str:
    high = IMPACT_SCORE.get(impact_level, 50) >= 50
    fast = velocity >= 50
    if high and fast:
        return "Prioritas utama"
    if high:
        return "Rencanakan"
    if fast:
        return "Pantau ketat"
    return "Pantau rutin"


def mention_card(row: Mention) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "source_name": row.source_name,
        "source_tier": row.source_tier,
        "platform": row.platform,
        "published_at": row.published_at.isoformat(timespec="minutes"),
        "stance": row.stance,
        "sentiment": row.sentiment,
        "reach_estimate": row.reach_estimate,
        "risk_score": row.risk_score,
        "category": row.category,
        "confidence": row.confidence,
        "is_kpw": row.is_kpw,
        "location": row.location,
        "status": row.status,
        "issue_id": row.issue_id,
        "url": row.url,
        "quotes_bi": bool(row.quotes_bi),
    }


def mention_detail(row: Mention) -> dict:
    data = mention_card(row)
    data.update(
        {
            "url": row.url,
            "author_name": row.author_name,
            "author_handle": row.author_handle,
            "text": row.text,
            "language": row.language,
            "likes": row.likes,
            "shares": row.shares,
            "comments": row.comments,
            "keyword_matches": loads(row.keyword_matches),
            "sentiment_score": row.sentiment_score,
            "rationale": row.rationale,
            "policy_relevance": row.policy_relevance,
            "policy_tags": loads(row.policy_tags),
            "spread_velocity": row.spread_velocity,
            "impact_level": row.impact_level,
            "credibility": row.credibility,
            "has_public_figure": row.has_public_figure,
            "needs_verification": row.needs_verification,
            "verification_note": row.verification_note,
            "pic": row.pic,
            "analyst_note": row.analyst_note,
            "human_corrected": row.human_corrected,
            "link_note": "Buka sumber asli",
        }
    )
    return data


def issue_card(row: Issue, mention_count: int = 0, last_at: str | None = None) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "title": row.title,
        "summary": row.summary,
        "category": row.category,
        "stance": row.stance,
        "sentiment": row.sentiment,
        "risk_score": row.risk_score,
        "policy_relevance": row.policy_relevance,
        "spread_velocity": row.spread_velocity,
        "impact_level": row.impact_level,
        "impact_score": IMPACT_SCORE.get(row.impact_level, 50),
        "quadrant": quadrant(row.impact_level, row.spread_velocity),
        "status": row.status,
        "pic": row.pic,
        "is_critical": row.is_critical,
        "is_kpw": row.is_kpw,
        "spike_detected": row.spike_detected,
        "policy_tags": loads(row.policy_tags),
        "started_at": row.started_at.isoformat(timespec="minutes"),
        "mention_count": mention_count,
        "last_at": last_at,
    }


def issue_detail(row: Issue, mention_count: int) -> dict:
    data = issue_card(row, mention_count)
    data.update(
        {
            "analyst_note": row.analyst_note,
            "ai_what": row.ai_what,
            "ai_who": row.ai_who,
            "ai_sentiment": row.ai_sentiment,
            "ai_impact": row.ai_impact,
            "ai_recommendation": row.ai_recommendation,
            "ai_note": "Ringkasan ini saran bacaan. Verifikasi sebelum dibawa ke rapat atau pernyataan resmi.",
        }
    )
    return data


def alert_out(row: Alert) -> dict:
    return {
        "id": row.id,
        "rule_id": row.rule_id,
        "title": row.title,
        "message": row.message,
        "severity": row.severity,
        "triggered_at": row.triggered_at.isoformat(timespec="minutes"),
        "is_read": row.is_read,
        "issue_id": row.issue_id,
    }
