"""Mengelompokkan mention nyata menjadi isu. Ringkasan hanya menyebut judul dan URL yang tersimpan."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Issue, Mention
from app.nlp.risk import score_risk
from app.services.clock import now_wib


def rebuild_issues(db: Session) -> int:
    since = now_wib() - timedelta(days=14)
    from app.services.blocklist import is_blocked, load_rules

    rules = load_rules(db)
    rows = [
        row
        for row in db.query(Mention).filter(Mention.published_at >= since).all()
        if not is_blocked(row.url, row.author_handle, row.author_name, row.source_name, row.title, rules)
    ]
    groups: dict[tuple[str, str], list[Mention]] = defaultdict(list)
    for row in rows:
        tags = json.loads(row.policy_tags or "[]")
        key = (row.category, tags[0] if tags else "Umum")
        groups[key].append(row)

    kept_codes: set[str] = set()
    created = 0
    for (category, tag), members in groups.items():
        if len(members) < 2:
            for member in members:
                member.issue_id = None
            continue
        members.sort(key=lambda item: item.published_at)
        code = _code(category, tag)
        kept_codes.add(code)
        issue = db.query(Issue).filter(Issue.code == code).one_or_none()
        if issue is None:
            issue = Issue(
                code=code,
                title=members[-1].title[:300],
                summary="",
                category=category,
                stance="netral",
                sentiment="netral",
                started_at=members[0].published_at,
                policy_tags=json.dumps([tag], ensure_ascii=False),
            )
            db.add(issue)
            db.flush()
            created += 1
        _fill_issue(issue, members, tag)
        for member in members:
            member.issue_id = issue.id
            member.spread_velocity = issue.spread_velocity
            member.impact_level = issue.impact_level
            if not member.human_corrected:
                member.risk_score = score_risk(
                    sentiment=member.sentiment,
                    stance=member.stance,
                    reach=member.reach_estimate,
                    source_tier=member.source_tier,
                    velocity=issue.spread_velocity,
                    has_public_figure=member.has_public_figure,
                    credibility=member.credibility,
                )
    for stale in db.query(Issue).all():
        if stale.code.startswith("LIVE-") and stale.code not in kept_codes and not stale.analyst_note:
            db.query(Mention).filter(Mention.issue_id == stale.id).update({Mention.issue_id: None})
            db.delete(stale)
    db.commit()
    return created


def _fill_issue(issue: Issue, members: list[Mention], tag: str) -> None:
    stance = _majority([item.stance for item in members])
    sentiment = _majority([item.sentiment for item in members])
    span = max(1.0, (members[-1].published_at - members[0].published_at).total_seconds() / 3600)
    velocity = round(min(100.0, len(members) / span * 18), 1)
    risk_values = [item.risk_score for item in members]
    risk = round(sum(risk_values) / len(risk_values), 1)
    links = [f"{item.source_name}: {item.title} — {item.url}" for item in members[:6]]
    issue.title = members[-1].title[:300]
    issue.summary = f"{len(members)} pemberitaan pada {tag}. Judul terbaru dipakai sebagai judul isu."
    issue.category = members[-1].category
    issue.stance = stance
    issue.sentiment = sentiment
    issue.risk_score = risk
    issue.policy_relevance = round(max(item.policy_relevance for item in members), 1)
    issue.spread_velocity = velocity
    issue.impact_level = "tinggi" if risk >= 70 or len(members) >= 6 else "sedang" if len(members) >= 3 else "rendah"
    issue.started_at = members[0].published_at
    issue.policy_tags = json.dumps(sorted({tag for item in members for tag in json.loads(item.policy_tags or "[]")}), ensure_ascii=False)
    issue.is_kpw = any(item.is_kpw for item in members)
    issue.is_critical = risk >= 75 and stance == "downside"
    issue.spike_detected = velocity >= 50 and len(members) >= 4
    issue.ai_what = "Ringkasan ini hanya menyusun judul yang benar-benar terkumpul.\n" + "\n".join(links)
    issue.ai_who = "Sumber: " + ", ".join(sorted({item.source_name for item in members}))
    issue.ai_sentiment = (
        f"Dari {len(members)} item: "
        f"{sum(item.sentiment == 'positif' for item in members)} positif, "
        f"{sum(item.sentiment == 'netral' for item in members)} netral, "
        f"{sum(item.sentiment == 'negatif' for item in members)} negatif."
    )
    issue.ai_impact = "Dampak dibaca dari sebaran nada pada judul dan cuplikan feed, bukan dari artikel penuh dan bukan dari fakta tambahan."
    issue.ai_recommendation = (
        "Saran komunikasi: buka setiap tautan sumber sebelum menyusun narasi. "
        + ("Nada downside lebih banyak. Siapkan klarifikasi hanya setelah fakta dicek pada sumber asli." if stance == "downside" else "Nada belum mengeras. Tetap cantumkan tautan saat membahas isu ini.")
    )


def _majority(values: list[str]) -> str:
    return max(set(values), key=values.count)


def _code(category: str, tag: str) -> str:
    raw = f"{category}-{tag}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return ("LIVE-" + slug)[:32]
