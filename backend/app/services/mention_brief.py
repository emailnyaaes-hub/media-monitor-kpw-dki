"""Brief 2–3 kalimat per konten — gaya ringkas analisis percakapan publik (selaras Drone Emprit).

Disusun hanya dari judul, cuplikan feed, klasifikasi, dan metadata yang tersimpan.
Tidak menambah fakta, angka, atau kutipan di luar sumber.
"""

from __future__ import annotations

import re

from app.models import Mention

_SNIPPET_PLACEHOLDERS = (
    "cuplikan tidak tersedia",
    "cuplikan tidak disertakan",
    "buka sumber asli",
)

_STANCE_LABEL = {
    "upside": "mendukung narasi positif terhadap kebijakan atau mandat Bank Indonesia",
    "downside": "berpotensi membebani persepsi atau reputasi Bank Indonesia",
    "netral": "bersifat informatif tanpa arah yang menonjol",
}

_SENTIMENT_LABEL = {
    "positif": "nada positif",
    "netral": "nada netral",
    "negatif": "nada negatif",
}


def build_mention_brief(row: Mention) -> str:
    """Bangun ringkasan 2–3 kalimat untuk satu mention."""
    title = (row.title or "").strip()
    snippet = _usable_snippet(row.text or "")
    category = row.category or "Lainnya"
    platform = (row.platform or "berita").strip()
    source = (row.source_name or "sumber eksternal").strip()
    stance = (row.stance or "netral").casefold()
    sentiment = (row.sentiment or "netral").casefold()
    tier = int(row.source_tier or 2)

    s1 = _opening_sentence(title, snippet, source, platform)
    s2 = _monitoring_sentence(category, sentiment, stance, tier, source, platform)
    s3 = _implication_sentence(row, category)

    parts = [s for s in (s1, s2, s3) if s]
    text = " ".join(parts)
    return _trim_brief(text)


def mention_brief_for_row(row: Mention) -> str:
    stored = (getattr(row, "brief", None) or "").strip()
    if stored:
        return stored
    return build_mention_brief(row)


def _usable_snippet(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if not t:
        return ""
    lower = t.casefold()
    if any(p in lower for p in _SNIPPET_PLACEHOLDERS):
        return ""
    return t


def _opening_sentence(title: str, snippet: str, source: str, platform: str) -> str:
    if snippet:
        lead = _first_sentence(snippet)
        if len(lead) < 40 and title:
            lead = f"{lead.rstrip('.')}; judul yang dipantau: «{title[:160]}»."
        elif not lead.endswith((".", "!", "?")):
            lead = lead.rstrip("…") + "."
        if lead[0].islower():
            lead = lead[0].upper() + lead[1:]
        return lead
    plat = {"berita": "artikel", "twitter": "unggahan X", "facebook": "unggahan Facebook"}.get(
        platform.casefold(), "konten"
    )
    return (
        f"{source} mempublikasikan {plat} berjudul «{title[:180]}» yang masuk kawasan pantauan "
        "Bank Indonesia/KPw DKI Jakarta."
    )


def _first_sentence(text: str) -> str:
    text = text.strip()
    for mark in (". ", "! ", "? ", ".\n"):
        idx = text.find(mark)
        if 80 <= idx <= 280:
            return text[: idx + 1].strip()
    if len(text) <= 280:
        return text
    cut = text[:260].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def _monitoring_sentence(
    category: str,
    sentiment: str,
    stance: str,
    tier: int,
    source: str,
    platform: str,
) -> str:
    sent_phrase = _SENTIMENT_LABEL.get(sentiment, "nada netral")
    stance_phrase = _STANCE_LABEL.get(stance, _STANCE_LABEL["netral"])
    tier_note = "media arus utama" if tier == 1 else "sumber daring"
    plat = platform if platform != "berita" else "portal berita"
    return (
        f"Pada kategori {category}, klasifikasi otomatis membaca {sent_phrase} dan posisi {stance_phrase}, "
        f"berasal dari {tier_note} {source} di {plat}."
    )


def _implication_sentence(row: Mention, category: str) -> str:
    if row.needs_verification:
        return (
            "Cuplikan atau judul memuat indikator hoaks/penipuan; verifikasi tautan asli wajib "
            "sebelum respons komunikasi atau eskalasi internal."
        )
    if row.quotes_bi:
        return (
            "Konten menyebut atau mengutip Bank Indonesia; pastikan interpretasi selaras "
            "dengan rilis dan kanal resmi sebelum dijadikan acuan keputusan."
        )
    if category == "Hoaks/Penipuan":
        return (
            "Isu berpotensi menyesatkan masyarakat; Koordinasi Kehumasan dan Unit Hukum "
            "disarankan bila pola serupa berulang di platform yang sama."
        )
    if category in {"Kebijakan Moneter", "Rupiah/Kurs", "Inflasi"}:
        return (
            "Perkembangan ini dipantau karena dapat membentuk persepsi pasar dan publik "
            "meski tidak menggantikan rilis kebijakan moneter resmi."
        )
    if row.is_kpw or category == "Kegiatan KPw DKI":
        return (
            "Narasi berkaitan wilayah kerja KPw DKI Jakarta; pantau eskalasi bila menyangkut "
            "program atau kegiatan di lapangan."
        )
    return (
        "Ringkasan disusun dari judul dan cuplikan feed, bukan artikel penuh—buka tautan "
        "untuk konteks dan kutipan lengkap."
    )


def _trim_brief(text: str, limit: int = 560) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rsplit(" ", 1)[0]
    if trimmed.endswith((".", "!", "?")):
        return trimmed
    return trimmed.rstrip(",;:") + "…"
