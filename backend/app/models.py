"""Tabel aplikasi.

Satu baris `mentions` = satu berita atau satu unggahan publik.
Satu baris `issues` = satu isu yang menaungi banyak mention.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    stance: Mapped[str] = mapped_column(String(16), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    policy_relevance: Mapped[float] = mapped_column(Float, default=0)
    spread_velocity: Mapped[float] = mapped_column(Float, default=0)
    impact_level: Mapped[str] = mapped_column(String(16), default="sedang")
    status: Mapped[str] = mapped_column(String(32), default="baru")
    pic: Mapped[str] = mapped_column(String(80), default="")
    analyst_note: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ai_what: Mapped[str] = mapped_column(Text, default="")
    ai_who: Mapped[str] = mapped_column(Text, default="")
    ai_sentiment: Mapped[str] = mapped_column(Text, default="")
    ai_impact: Mapped[str] = mapped_column(Text, default="")
    ai_recommendation: Mapped[str] = mapped_column(Text, default="")
    policy_tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON string
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    is_kpw: Mapped[bool] = mapped_column(Boolean, default=False)
    spike_detected: Mapped[bool] = mapped_column(Boolean, default=False)


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_tier: Mapped[int] = mapped_column(Integer, default=2)  # 1 = media arus utama
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String(400), default="")
    author_name: Mapped[str] = mapped_column(String(120), default="")
    author_handle: Mapped[str] = mapped_column(String(120), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(8), default="id")
    likes: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    reach_estimate: Mapped[int] = mapped_column(Integer, default=0)
    keyword_matches: Mapped[str] = mapped_column(Text, default="[]")
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0)  # -1 s.d. 1
    stance: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    policy_relevance: Mapped[float] = mapped_column(Float, default=0)
    policy_tags: Mapped[str] = mapped_column(Text, default="[]")
    spread_velocity: Mapped[float] = mapped_column(Float, default=0)
    impact_level: Mapped[str] = mapped_column(String(16), default="sedang")
    credibility: Mapped[int] = mapped_column(Integer, default=60)
    has_public_figure: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_note: Mapped[str] = mapped_column(Text, default="")
    is_kpw: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="baru")
    pic: Mapped[str] = mapped_column(String(80), default="")
    analyst_note: Mapped[str] = mapped_column(Text, default="")
    human_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    quotes_bi: Mapped[bool] = mapped_column(Boolean, default=False)
    issue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issues.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Keyword(Base):
    __tablename__ = "keywords"
    __table_args__ = (UniqueConstraint("term", "mode", name="uq_keyword_term_mode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # inklusi | eksklusi
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BlockedSource(Base):
    """Domain, akun, atau nama kanal milik Bank Indonesia yang tidak boleh masuk mention."""

    __tablename__ = "blocked_sources"
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_blocked_kind_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # domain | account | channel
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str] = mapped_column(String(240), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SavedQuery(Base):
    """Ekspresi boolean yang disimpan pengguna, misalnya: QRIS AND NOT lowongan."""

    __tablename__ = "saved_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, default=0)
    window_hours: Mapped[int] = mapped_column(Integer, default=24)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    keyword: Mapped[str] = mapped_column(String(160), default="")
    channel: Mapped[str] = mapped_column(String(32), default="dashboard")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alert_rules.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    issue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issues.id"), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)


class ChannelPost(Base):
    """Konten kanal resmi KPw untuk mengukur performa kehumasan, terpisah dari mention publik."""

    __tablename__ = "channel_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0)


class ConnectorRun(Base):
    """Jejak setiap percobaan mengambil satu sumber. Kegagalan disimpan, tidak diganti data lain."""

    __tablename__ = "connector_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    found: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Advice(Base):
    """Saran pendukung keputusan. Bukan tindakan otomatis ke publik."""

    __tablename__ = "advices"
    __table_args__ = (UniqueConstraint("stable_key", name="uq_advice_stable_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # respons | prioritas | kebijakan | peluang | mitigasi
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    situation: Mapped[str] = mapped_column(Text, default="")
    who: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(String(160), default="")
    urgency: Mapped[str] = mapped_column(String(16), default="rendah")
    reason: Mapped[str] = mapped_column(Text, default="")
    impact_follow: Mapped[str] = mapped_column(Text, default="")
    impact_ignore: Mapped[str] = mapped_column(Text, default="")
    alternatives: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[str] = mapped_column(String(16), default="rendah")
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    source_diversity: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[str] = mapped_column(Text, default="[]")
    facts: Mapped[str] = mapped_column(Text, default="[]")
    inferences: Mapped[str] = mapped_column(Text, default="[]")
    public_voice: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(String(160), default="Kehumasan")
    draft_points: Mapped[str] = mapped_column(Text, default="")
    draft_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    insufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="baru")
    analyst_note: Mapped[str] = mapped_column(Text, default="")
    useful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    feedback_reason: Mapped[str] = mapped_column(Text, default="")
    issue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("issues.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="")
    policy_topic: Mapped[str] = mapped_column(String(80), default="")
    model_name: Mapped[str] = mapped_column(String(80), default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    evidence_hash: Mapped[str] = mapped_column(String(64), default="")
    change_note: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AdviceRevision(Base):
    """Riwayat saran. Baris tidak dihapus saat siklus berikutnya."""

    __tablename__ = "advice_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advice_id: Mapped[int] = mapped_column(ForeignKey("advices.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    urgency: Mapped[str] = mapped_column(String(16), default="")
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
