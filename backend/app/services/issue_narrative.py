"""Ringkasan isu dan saran komunikasi — selalu dihasilkan (bukan bergantung LLM_API_KEY).

Mengisi kolom ai_* pada Issue dengan ragam Bank Indonesia. Jika LLM_API_KEY ada,
teks dasar dapat diperhalus model, tetapi fallback ini tetap komprehensif.
"""

from __future__ import annotations

import json
import os
from collections import Counter

from app.services.dss_llm import _complete, _parse_json


def fill_ai_fields(issue, members: list) -> None:
    if not members:
        return
    members = sorted(members, key=lambda item: item.published_at)
    base = _rule_based(members, issue)
    enriched = _maybe_llm_enrich(members, base)
    if enriched:
        base = enriched
    issue.ai_what = base["what"]
    issue.ai_who = base["who"]
    issue.ai_sentiment = base["sentiment"]
    issue.ai_impact = base["impact"]
    issue.ai_recommendation = base["recommendation"]
    issue.summary = base.get("summary", issue.summary) or issue.summary


def _rule_based(members: list, issue) -> dict:
    category = issue.category or members[-1].category or "Lainnya"
    title = issue.title or members[-1].title
    start = members[0].published_at.strftime("%d %b %Y")
    end = members[-1].published_at.strftime("%d %b %Y")
    sources = sorted({m.source_name for m in members if m.source_name})
    tier1 = sorted({m.source_name for m in members if m.source_tier == 1})
    pos = sum(m.sentiment == "positif" for m in members)
    neu = sum(m.sentiment == "netral" for m in members)
    neg = sum(m.sentiment == "negatif" for m in members)
    stance = issue.stance or "netral"
    tags = []
    for m in members:
        tags.extend(json.loads(m.policy_tags or "[]"))
    tag_top = Counter(tags).most_common(1)[0][0] if tags else "umum"
    latest = members[-1]
    what = (
        f"Bank Indonesia mencatat {len(members)} konten eksternal pada periode {start}–{end} "
        f"terkait \"{title}\" (kategori {category}, topik {tag_top}). "
        f"Perkembangan terkini: {latest.source_name} menurunkan judul \"{latest.title[:160]}\" "
        f"pada {latest.published_at.strftime('%d %b %Y')}. "
        "Narasi disusun dari judul dan cuplikan yang tersimpan, bukan dari artikel penuh."
    )
    who = (
        "Sumber yang teridentifikasi: " + ", ".join(sources[:10])
        + (f". Media arus utama: {', '.join(tier1)}." if tier1 else ". Belum ada media tier-1 pada klaster ini.")
    )
    sentiment = (
        f"Dari {len(members)} item terklasifikasi: {pos} positif, {neu} netral, {neg} negatif. "
        f"Label dominan: {stance}. "
        "Komposisi ini menghitung klasifikasi otomatis, bukan survei sentimen resmi."
    )
    impact = _impact_text(stance, neg, len(members), category, issue.is_critical, issue.spread_velocity or 0)
    recommendation = _recommendation_text(stance, neg, tier1, category, tag_top, members, issue.impact_level or "sedang")
    summary = (
        f"{len(members)} pemberitaan pada {tag_top}. "
        f"Bank Indonesia/KPw memantau persepsi publik; rekomendasi komunikasi tersedia di bawah setelah verifikasi bukti."
    )
    return {
        "what": what,
        "who": who,
        "sentiment": sentiment,
        "impact": impact,
        "recommendation": recommendation,
        "summary": summary,
    }


def _impact_text(stance: str, neg: int, total: int, category: str, critical: bool, velocity: float) -> str:
    neg_pct = round(100 * neg / total) if total else 0
    parts = [
        f"Dampak dibaca pada dimensi persepsi: {neg_pct}% konten bernada negatif.",
    ]
    if category in {"Hoaks/Penipuan", "Reputasi/Kelembagaan"}:
        parts.append(
            "KRITIS: isu menyentuh kredibilitas kanal resmi Bank Indonesia dan berpotensi menyesatkan masyarakat "
            "bila tidak segera diklarifikasi sesuai mandat edukasi dan perlindungan konsumen."
        )
    elif category in {"Kebijakan Moneter", "Rupiah/Kurs", "Inflasi"}:
        parts.append(
            "Persepsi dapat memengaruhi pemahaman publik terhadap kebijakan moneter dan stabilitas nilai tukar rupiah, "
            "meskipun tidak mengukur dampak kebijakan secara kuantitatif."
        )
    elif category == "Sistem Pembayaran":
        parts.append(
            "Kepercayaan pada sistem pembayaran sensitif; gangguan atau hoaks layanan (QRIS, BI-FAST) perlu respons "
            "yang cepat, factual, dan selaras dengan kanal operasional Bank Indonesia."
        )
    if critical or (stance == "downside" and neg >= 2):
        parts.append(
            "Tingkat eskalasi dinilai meningkat; koordinasi Kehumasan dengan Unit Hukum disarankan sebelum pernyataan publik."
        )
    if velocity >= 50:
        parts.append(f"Kecepatan sebar {velocity:.0f} menandakan isu berpotensi membesar dalam 24–48 jam.")
    return " ".join(parts)


def _recommendation_text(
    stance: str,
    neg: int,
    tier1: list[str],
    category: str,
    tag_top: str,
    members: list,
    impact_level: str,
) -> str:
    verify = any(m.needs_verification for m in members)
    hoaks = category == "Hoaks/Penipuan" or any("hoaks" in f"{m.title} {m.text}".casefold() for m in members)
    urgency = "24 jam" if hoaks or impact_level == "tinggi" else "48–72 jam"
    lines = [
        "Saran komunikasi internal (bukan pernyataan resmi otomatis):",
        f"1. Kehumasan/KPw BI DKI Jakarta memverifikasi seluruh tautan bukti dan menyelaraskan fakta dengan juru bicara yang berwenang.",
    ]
    if verify or hoaks:
        lines.append(
            f"2. KRITIS: tunda penyebaran narasi hingga penanda hoaks/penipuan selesai dicek; "
            f"siapkan draf klarifikasi singkat untuk kanal resmi dalam {urgency}."
        )
    elif stance == "downside" or neg >= len(members) // 2:
        channel = (
            "siaran pers atau penjelasan ke media arus utama"
            if tier1
            else "media sosial resmi Bank Indonesia dan KPw DKI Jakarta"
        )
        lines.append(
            f"2. Susun draf {channel} yang menegaskan fakta resmi tanpa mengubah kebijakan moneter; "
            "hindari angka operasi atau prakiraan yang tidak ada di rilis resmi."
        )
    else:
        lines.append(
            "2. Manfaatkan momentum untuk edukasi (sistem pembayaran, inflasi, atau program KPw) dengan bahasa baku Indonesia."
        )
    lines.append(
        "3. Pantau ulang komposisi sentimen setelah tindakan; eskalasikan ke pimpinan bila media tier-1 membawa narasi downside baru."
    )
    lines.append(f"Topik kebijakan yang terbaca: {tag_top}. Koordinasi unit terkait sesuai matriks internal.")
    return "\n".join(lines)


def _maybe_llm_enrich(members: list, base: dict) -> dict | None:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key or len(members) < 2:
        return None
    snippets = []
    for m in members[:8]:
        snippets.append(f"- {m.source_name}: {m.title}")
    user = json.dumps({"ringkasan_dasar": base, "cuplikan": snippets}, ensure_ascii=False)
    system = (
        "Anda penyusun notula Kehumasan Bank Indonesia. Perkaya ringkasan dengan ragam siaran pers BI. "
        "Jangan menambah fakta, angka, atau URL. Kembalikan JSON dengan kunci: what, who, sentiment, impact, recommendation. "
        "Sertakan KRITIS dan langkah bernomor pada recommendation. Maksimal 120 kata per field kecuali recommendation."
    )
    raw = _complete(system, user, key)
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        parsed = _parse_json(raw)
        data = parsed
    if not isinstance(data, dict):
        return None
    out = dict(base)
    for field in ("what", "who", "sentiment", "impact", "recommendation"):
        if data.get(field):
            out[field] = str(data[field])[:2500]
    return out
