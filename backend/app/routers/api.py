"""Titik masuk HTTP. Satu berkas agar alur permintaan mudah ditelusuri tim."""

from __future__ import annotations

from typing import Optional

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (
    CurrentUser,
    create_token,
    get_current_user,
    require_admin,
    require_writer,
    verify_password,
)
from app.constants import (
    CATEGORIES,
    DISCLAIMER,
    PLATFORMS,
    ROLE_LABELS,
    SEVERITIES,
    STATUSES,
    STATUS_LABELS,
)
from app.database import get_db
from app.models import Alert, AlertRule, AppMeta, AuditLog, BlockedSource, Issue, Keyword, Mention, SavedQuery, User
from app.nlp import analyze
from app.nlp.config_store import get_config, save_config
from app.nlp.prompts import CLASSIFY_PROMPT, SUMMARY_PROMPT
from app.nlp.boolean import ExpressionError, match_expression
from app.nlp.risk import score_risk
from app.services import analytics
from app.services.blocklist import apply_blocklist, external_only, load_rules
from app.services.alerts import evaluate_rules
from app.services.pipeline import ingest, retag, status_payload
from app.services.reports import csv_mentions, html_report, narrative, pptx_report, workbook
from app.services.serialize import alert_out, issue_detail, loads, mention_card, mention_detail

router = APIRouter()


class LoginBody(BaseModel):
    username: str
    password: str


class MentionPatch(BaseModel):
    sentiment: Optional[str] = None
    stance: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    pic: Optional[str] = Field(default=None, max_length=80)
    analyst_note: Optional[str] = Field(default=None, max_length=2000)


class IssuePatch(BaseModel):
    status: Optional[str] = None
    pic: Optional[str] = Field(default=None, max_length=80)
    analyst_note: Optional[str] = Field(default=None, max_length=2000)


class KeywordBody(BaseModel):
    term: str = Field(min_length=2, max_length=160)
    category: str
    mode: str
    is_active: bool = True


class QueryBody(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    expression: str = Field(min_length=2)
    is_active: bool = True


class RuleBody(BaseModel):
    name: str
    rule_type: str
    threshold: float = 0
    window_hours: int = 24
    severity: str = "info"
    keyword: str = ""
    channel: str = "dashboard"
    is_active: bool = True


class ClassifyBody(BaseModel):
    text: str = Field(min_length=4)
    reach: int = 10000
    source_tier: int = 2
    velocity: float = 40


class ExpressionTest(BaseModel):
    expression: str
    text: str


class ConfigBody(BaseModel):
    weights: dict
    thresholds: Optional[dict] = None


def _window(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    try:
        return analytics.parse_window(date_from, date_to, platform, category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _audit(db: Session, actor: str, action: str, entity_type: str, entity_id: int | str, old: str, new: str) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            old_value=old[:2000],
            new_value=new[:2000],
        )
    )


@router.get("/health")
def health(db: Session = Depends(get_db)):
    mode = db.get(AppMeta, "data_mode")
    seeded = db.get(AppMeta, "seeded_at")
    return {
        "status": "ok",
        "mode": mode.value if mode else "unknown",
        "seeded_at": seeded.value if seeded else None,
        "mentions": external_only(db.query(Mention), load_rules(db)).count(),
        "disclaimer": DISCLAIMER,
    }


@router.post("/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip()).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Nama pengguna atau sandi salah")
    return {
        "token": create_token(user),
        "user": {"username": user.username, "full_name": user.full_name, "role": user.role, "role_label": ROLE_LABELS[user.role]},
    }


@router.get("/auth/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {"username": user.username, "full_name": user.full_name, "role": user.role, "role_label": ROLE_LABELS[user.role]}


@router.get("/meta")
def meta(_: CurrentUser = Depends(get_current_user)):
    return {
        "categories": CATEGORIES,
        "platforms": [{"id": key, "label": label} for key, label in PLATFORMS],
        "statuses": [{"id": key, "label": label} for key, label in STATUS_LABELS.items()],
        "severities": SEVERITIES,
        "disclaimer": DISCLAIMER,
        "mode": "live",
    }


@router.get("/overview")
def get_overview(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    window = _window(date_from, date_to, platform, category)
    data = analytics.overview(db, window)
    data["active_alerts"] = [
        alert_out(row)
        for row in db.query(Alert).filter(Alert.is_read.is_(False)).order_by(Alert.triggered_at.desc()).limit(5).all()
    ]
    seeded = db.get(AppMeta, "last_ingest_at")
    mode = db.get(AppMeta, "data_mode")
    data["mode"] = mode.value if mode else "live"
    data["seeded_at"] = seeded.value if seeded else None
    data["disclaimer"] = DISCLAIMER
    return data


@router.get("/trend")
def get_trend(
    granularity: str = "day",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    if granularity not in {"day", "week", "month"}:
        raise HTTPException(status_code=400, detail="Granularitas harus day, week, atau month")
    return {"items": analytics.trend(db, _window(date_from, date_to, platform, category), granularity)}


@router.get("/mentions")
def get_mentions(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    sentiment: Optional[str] = None,
    stance: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    min_risk: Optional[float] = None,
    issue_id: Optional[int] = None,
    kpw: bool = False,
    sort: str = "terbaru",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    window = _window(date_from, date_to, platform, category)
    return analytics.search_mentions(
        db,
        window,
        {
            "q": q,
            "sentiment": sentiment,
            "stance": stance,
            "status": status,
            "source": source,
            "keyword": keyword,
            "min_risk": min_risk,
            "issue_id": issue_id,
            "kpw": kpw,
            "sort": sort,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/mentions/{mention_id}")
def get_mention(mention_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    row = db.get(Mention, mention_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Mention tidak ditemukan")
    data = mention_detail(row)
    data["audit"] = [
        {
            "actor": item.actor,
            "action": item.action,
            "old_value": item.old_value,
            "new_value": item.new_value,
            "created_at": item.created_at.isoformat(timespec="minutes"),
        }
        for item in db.query(AuditLog)
        .filter(AuditLog.entity_type == "mention", AuditLog.entity_id == str(mention_id))
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    ]
    return data


@router.patch("/mentions/{mention_id}")
def patch_mention(
    mention_id: int,
    body: MentionPatch,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_writer),
):
    row = db.get(Mention, mention_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Mention tidak ditemukan")
    changes = body.model_dump(exclude_none=True)
    if not changes:
        return mention_detail(row)
    if "sentiment" in changes and changes["sentiment"] not in {"positif", "netral", "negatif"}:
        raise HTTPException(status_code=400, detail="Sentimen tidak dikenali")
    if "stance" in changes and changes["stance"] not in {"upside", "netral", "downside"}:
        raise HTTPException(status_code=400, detail="Stance tidak dikenali")
    if "category" in changes and changes["category"] not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Kategori tidak dikenali")
    if "status" in changes and changes["status"] not in STATUSES:
        raise HTTPException(status_code=400, detail="Status tidak dikenali")
    old = {key: getattr(row, key) for key in changes}
    for key, value in changes.items():
        setattr(row, key, value)
    label_fields = {"sentiment", "stance", "category"} & set(changes)
    if label_fields:
        row.human_corrected = True
        row.confidence = 1
        note = changes.get("analyst_note") or "label diperbarui analis"
        row.rationale = f"[Koreksi analis] {note}"
        row.risk_score = score_risk(
            sentiment=row.sentiment,
            stance=row.stance,
            reach=row.reach_estimate,
            source_tier=row.source_tier,
            velocity=row.spread_velocity,
            has_public_figure=row.has_public_figure,
            credibility=row.credibility,
        )
    _audit(db, user.username, "ubah_mention", "mention", row.id, json.dumps(old, ensure_ascii=False), json.dumps(changes, ensure_ascii=False))
    db.commit()
    db.refresh(row)
    return mention_detail(row)


@router.get("/issues")
def get_issues(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    kpw: bool = False,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return {"items": analytics.list_issues(db, _window(date_from, date_to, platform, category), kpw_only=kpw)}


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    row = db.get(Issue, issue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Isu tidak ditemukan")
    mentions = external_only(
        db.query(Mention).filter(Mention.issue_id == row.id).order_by(Mention.published_at.asc()),
        load_rules(db),
    ).all()
    data = issue_detail(row, len(mentions))
    data["timeline"] = [mention_card(item) for item in mentions]
    data["timeline_note"] = "Linimasa menampilkan seluruh riwayat isu, tidak dipotong filter tanggal."
    from app.services.dss import advice_timeline, list_advices

    advice_payload = list_advices(db, {"issue_id": row.id})
    for item in advice_payload["items"]:
        item["timeline"] = advice_timeline(db, item["id"])
    data["advices"] = advice_payload["items"]
    data["advice_disclaimer"] = advice_payload["disclaimer"]
    return data


@router.patch("/issues/{issue_id}")
def patch_issue(
    issue_id: int,
    body: IssuePatch,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_writer),
):
    row = db.get(Issue, issue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Isu tidak ditemukan")
    changes = body.model_dump(exclude_none=True)
    if "status" in changes and changes["status"] not in STATUSES:
        raise HTTPException(status_code=400, detail="Status tidak dikenali")
    old = {key: getattr(row, key) for key in changes}
    for key, value in changes.items():
        setattr(row, key, value)
    _audit(db, user.username, "ubah_isu", "issue", row.id, json.dumps(old, ensure_ascii=False), json.dumps(changes, ensure_ascii=False))
    db.commit()
    db.refresh(row)
    mentions = db.query(Mention).filter(Mention.issue_id == row.id).count()
    return issue_detail(row, mentions)


@router.get("/topics")
def get_topics(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return analytics.topics(db, _window(date_from, date_to, platform, category))


@router.get("/topics/related")
def get_related(
    term: str = Query(min_length=2),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return {"term": term, "items": analytics.related_words(db, _window(date_from, date_to, platform, category), term)}


@router.get("/radar")
def get_radar(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return {"items": analytics.radar(db, _window(date_from, date_to, platform, category))}


@router.get("/policy-feedback")
def get_policy(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return {"items": analytics.policy_feedback(db, _window(date_from, date_to, platform, category))}


@router.get("/sentiment/breakdown")
def sentiment_breakdown(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return {"items": analytics.category_breakdown(db, _window(date_from, date_to, platform, category))}


@router.get("/kpw")
def get_kpw(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    window = _window(date_from, date_to, platform, category)
    data = analytics.kpw_overview(db, window)
    data["channels"] = {"summary": [], "posts": [], "status": "dihapus", "message": ""}
    return data


@router.get("/sources")
def get_sources(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    window = _window(date_from, date_to, platform, category)
    return {"media": analytics.media_ranking(db, window), "influencers": analytics.influencers(db, window)}


@router.get("/keywords")
def get_keywords(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    rows = db.query(Keyword).order_by(Keyword.category, Keyword.term).all()
    queries = db.query(SavedQuery).order_by(SavedQuery.id).all()
    return {
        "items": [
            {"id": row.id, "term": row.term, "category": row.category, "mode": row.mode, "is_active": row.is_active}
            for row in rows
        ],
        "queries": [
            {"id": row.id, "name": row.name, "expression": row.expression, "is_active": row.is_active}
            for row in queries
        ],
    }


@router.post("/keywords")
def add_keyword(body: KeywordBody, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    if body.mode not in {"inklusi", "eksklusi"}:
        raise HTTPException(status_code=400, detail="Mode harus inklusi atau eksklusi")
    exists = db.query(Keyword).filter(Keyword.term == body.term.strip(), Keyword.mode == body.mode).first()
    if exists:
        raise HTTPException(status_code=409, detail="Kata kunci yang sama sudah ada")
    row = Keyword(term=body.term.strip(), category=body.category.strip(), mode=body.mode, is_active=body.is_active)
    db.add(row)
    _audit(db, user.username, "tambah_kata", "keyword", body.term, "", body.mode)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "term": row.term, "category": row.category, "mode": row.mode, "is_active": row.is_active}


@router.patch("/keywords/{keyword_id}")
def patch_keyword(
    keyword_id: int,
    body: KeywordBody,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    row = db.get(Keyword, keyword_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Kata kunci tidak ditemukan")
    old = row.term
    row.term = body.term.strip()
    row.category = body.category.strip()
    row.mode = body.mode
    row.is_active = body.is_active
    _audit(db, user.username, "ubah_kata", "keyword", row.id, old, row.term)
    db.commit()
    return {"id": row.id, "term": row.term, "category": row.category, "mode": row.mode, "is_active": row.is_active}


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    row = db.get(Keyword, keyword_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Kata kunci tidak ditemukan")
    _audit(db, user.username, "hapus_kata", "keyword", row.id, row.term, "")
    db.delete(row)
    db.commit()
    return {"ok": True}


class BlockBody(BaseModel):
    kind: str
    value: str
    note: str = ""
    is_active: bool = True


def _block_out(row: BlockedSource) -> dict:
    return {"id": row.id, "kind": row.kind, "value": row.value, "note": row.note, "is_active": row.is_active}


@router.get("/blocklist")
def get_blocklist(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    rows = db.query(BlockedSource).order_by(BlockedSource.kind, BlockedSource.value).all()
    return {"items": [_block_out(row) for row in rows]}


@router.post("/blocklist")
def add_block(body: BlockBody, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    kind = body.kind.strip()
    value = body.value.strip()
    if kind not in {"domain", "account", "channel"} or not value:
        raise HTTPException(status_code=400, detail="Jenis harus domain, account, atau channel, dan nilai tidak boleh kosong")
    if db.query(BlockedSource).filter(BlockedSource.kind == kind, BlockedSource.value == value).first():
        raise HTTPException(status_code=409, detail="Entri blokir yang sama sudah ada")
    row = BlockedSource(kind=kind, value=value, note=body.note.strip(), is_active=body.is_active)
    db.add(row)
    _audit(db, user.username, "tambah_blokir", "blocked_source", value, "", kind)
    db.commit()
    removed = apply_blocklist(db)
    db.refresh(row)
    payload = _block_out(row)
    payload["removed"] = removed
    return payload


@router.patch("/blocklist/{block_id}")
def patch_block(
    block_id: int,
    body: BlockBody,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    row = db.get(BlockedSource, block_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Entri blokir tidak ditemukan")
    if body.kind.strip() not in {"domain", "account", "channel"}:
        raise HTTPException(status_code=400, detail="Jenis harus domain, account, atau channel")
    row.kind = body.kind.strip()
    row.value = body.value.strip()
    row.note = body.note.strip()
    row.is_active = body.is_active
    _audit(db, user.username, "ubah_blokir", "blocked_source", row.id, "", row.value)
    db.commit()
    removed = apply_blocklist(db)
    payload = _block_out(row)
    payload["removed"] = removed
    return payload


@router.delete("/blocklist/{block_id}")
def delete_block(block_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    row = db.get(BlockedSource, block_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Entri blokir tidak ditemukan")
    _audit(db, user.username, "hapus_blokir", "blocked_source", row.id, row.value, "")
    db.delete(row)
    db.commit()
    return {"ok": True, "removed": apply_blocklist(db)}


@router.post("/keyword-queries")
def add_query(body: QueryBody, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    try:
        match_expression(body.expression, "uji")
    except ExpressionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = SavedQuery(name=body.name.strip(), expression=body.expression.strip(), is_active=body.is_active)
    db.add(row)
    _audit(db, user.username, "tambah_ekspresi", "query", body.name, "", body.expression)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "expression": row.expression, "is_active": row.is_active}


@router.post("/keyword-queries/test")
def test_query(body: ExpressionTest, _: CurrentUser = Depends(get_current_user)):
    try:
        matched = match_expression(body.expression, body.text)
    except ExpressionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"matched": matched}


@router.delete("/keyword-queries/{query_id}")
def delete_query(query_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    row = db.get(SavedQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ekspresi tidak ditemukan")
    _audit(db, user.username, "hapus_ekspresi", "query", row.id, row.expression, "")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    rows = db.query(Alert).order_by(Alert.triggered_at.desc()).limit(50).all()
    rules = db.query(AlertRule).order_by(AlertRule.id).all()
    return {
        "items": [alert_out(row) for row in rows],
        "unread": sum(1 for row in rows if not row.is_read),
        "rules": [
            {
                "id": row.id,
                "name": row.name,
                "rule_type": row.rule_type,
                "threshold": row.threshold,
                "window_hours": row.window_hours,
                "severity": row.severity,
                "keyword": row.keyword,
                "channel": row.channel,
                "is_active": row.is_active,
            }
            for row in rules
        ],
        "channel_note": "Email, WhatsApp, dan Telegram disiapkan pada model data, tetapi pengirimannya belum diaktifkan.",
    }


@router.patch("/alerts/{alert_id}/read")
def read_alert(alert_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(require_writer)):
    row = db.get(Alert, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Alert tidak ditemukan")
    row.is_read = True
    db.commit()
    return alert_out(row)


@router.post("/alert-rules")
def add_rule(body: RuleBody, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    if body.severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail="Tingkat keparahan tidak dikenali")
    if body.rule_type not in {"negative_growth", "keyword_count", "tier1_downside", "kpw_negative", "volume_spike"}:
        raise HTTPException(status_code=400, detail="Jenis aturan tidak dikenali")
    row = AlertRule(**body.model_dump())
    db.add(row)
    _audit(db, user.username, "tambah_aturan", "alert_rule", body.name, "", body.rule_type)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.patch("/alert-rules/{rule_id}")
def patch_rule(rule_id: int, body: RuleBody, db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)):
    row = db.get(AlertRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Aturan tidak ditemukan")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return {"id": row.id, "is_active": row.is_active}


@router.post("/classify")
def classify(body: ClassifyBody, _: CurrentUser = Depends(get_current_user)):
    result = analyze(
        body.text,
        reach=body.reach,
        source_tier=body.source_tier,
        velocity=body.velocity,
    )
    result.pop("normalized_text", None)
    return result


@router.get("/nlp/config")
def read_config(_: CurrentUser = Depends(get_current_user)):
    return {"config": get_config(), "classify_prompt": CLASSIFY_PROMPT, "summary_prompt": SUMMARY_PROMPT}


@router.put("/nlp/config")
def write_config(body: ConfigBody, _: CurrentUser = Depends(require_admin)):
    try:
        saved = save_config(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"config": saved}


@router.get("/reports/summary")
def report_summary(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return narrative(db, _window(date_from, date_to, platform, category))


@router.get("/export/mentions.csv")
def export_csv(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    sentiment: Optional[str] = None,
    stance: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    text = csv_mentions(
        db,
        _window(date_from, date_to, platform, category),
        {"q": q, "sentiment": sentiment, "stance": stance, "status": status, "sort": "terbaru"},
    )
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=mention-media-monitor.csv"},
    )


@router.get("/export/laporan.xlsx")
def export_xlsx(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    payload = workbook(db, _window(date_from, date_to, platform, category))
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=laporan-media-monitor.xlsx"},
    )


@router.get("/export/laporan.pptx")
def export_pptx(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    payload = pptx_report(db, _window(date_from, date_to, platform, category))
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": "attachment; filename=laporan-media-monitor.pptx"},
    )


@router.get("/export/laporan.html", response_class=HTMLResponse)
def export_html(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return html_report(db, _window(date_from, date_to, platform, category))


@router.get("/ingest/status")
def ingest_status(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    return status_payload(db)


@router.post("/jobs/ingest")
def job_ingest(db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)):
    return ingest(db)


@router.post("/jobs/retag")
def job_retag(db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)):
    return {"updated": retag(db)}


@router.post("/jobs/evaluate-alerts")
def job_alerts(db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)):
    return {"created": evaluate_rules(db)}


@router.post("/jobs/reset-demo")
def job_reset(_: CurrentUser = Depends(require_admin)):
    raise HTTPException(status_code=410, detail="Pengisian data contoh dinonaktifkan. Gunakan Perbarui sekarang untuk mengambil sumber asli.")


@router.get("/advices")
def get_advices(
    urgency: Optional[str] = None,
    kind: Optional[str] = None,
    category: Optional[str] = None,
    unit: Optional[str] = None,
    status: Optional[str] = None,
    issue_id: Optional[int] = None,
    top: int = 0,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    from app.services.dss import list_advices

    return list_advices(
        db,
        {"urgency": urgency, "kind": kind, "category": category, "unit": unit, "status": status, "issue_id": issue_id},
        top=top,
    )


@router.get("/advices/{advice_id}/timeline")
def get_advice_timeline(advice_id: int, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    from app.services.dss import advice_timeline

    return {"items": advice_timeline(db, advice_id)}


class AdviceAction(BaseModel):
    action: str
    analyst_note: str = ""
    draft_points: str = ""
    useful: Optional[bool] = None
    feedback_reason: str = ""
    unit: str = ""


@router.post("/advices/{advice_id}/actions")
def post_advice_action(
    advice_id: int,
    body: AdviceAction,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_writer),
):
    from app.services.dss import act

    result = act(db, advice_id, body.model_dump(), user.username)
    if not result:
        raise HTTPException(status_code=404, detail="Saran tidak ditemukan atau aksi tidak dikenali")
    return result


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/dss/ask")
def post_ask(body: AskBody, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    from app.services.dss import ask

    return ask(db, body.question.strip())


class SimulateBody(BaseModel):
    issue_id: Optional[int] = None


@router.post("/dss/simulate")
def post_simulate(body: SimulateBody, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    from app.services.dss import simulate

    return simulate(db, body.issue_id)


@router.get("/dss/config")
def get_dss_config(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    from app.services.dss import load_settings

    return load_settings(db)


class DssConfigBody(BaseModel):
    min_sources: int = 3
    urgent_risk: float = 70
    credibility_weight: float = 1
    tone: str = "formal netral"


@router.put("/dss/config")
def put_dss_config(body: DssConfigBody, db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    from app.services.dss import refresh_advices, save_settings

    saved = save_settings(db, body.model_dump())
    _audit(db, user.username, "ubah_dss", "dss_config", "config", "", json.dumps(saved))
    db.commit()
    refresh_advices(db)
    return saved


@router.post("/jobs/refresh-advices")
def job_refresh_advices(db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)):
    from app.services.dss import refresh_advices

    return refresh_advices(db)


@router.get("/export/briefing.html")
def export_briefing_html(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    from app.services.dss_export import briefing_html

    return HTMLResponse(briefing_html(db))


@router.get("/export/briefing.pptx")
def export_briefing_pptx(db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    from app.services.dss_export import briefing_pptx

    return Response(
        content=briefing_pptx(db),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": "attachment; filename=briefing-pimpinan.pptx"},
    )


@router.get("/export/masukan-kebijakan.html")
def export_policy_html(
    topic: str = "",
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    from app.services.dss_export import policy_html

    return HTMLResponse(policy_html(db, topic))


@router.get("/audit")
def get_audit(db: Session = Depends(get_db), _: CurrentUser = Depends(require_admin)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(40).all()
    return {
        "items": [
            {
                "actor": row.actor,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "old_value": row.old_value,
                "new_value": row.new_value,
                "created_at": row.created_at.isoformat(timespec="minutes"),
            }
            for row in rows
        ]
    }
