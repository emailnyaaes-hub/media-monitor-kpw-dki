"""Skor risiko reputasi dan relevansi kebijakan.

Rumus ini sengaja sederhana dan bisa diubah dari layar Pengaturan
atau berkas data/nlp_config.json. Jangan mengubah rumus di dua tempat:
API membaca angka bobot dari konfigurasi, lalu memanggil fungsi di sini.
"""

from __future__ import annotations

import math

from app.nlp.config_store import get_config

# Istilah yang menautkan sebuah teks ke kebijakan BI tertentu.
POLICY_GROUPS: dict[str, list[str]] = {
    "BI-Rate": ["bi-rate", "suku bunga acuan", "suku bunga"],
    "Nilai tukar": ["nilai tukar", "rupiah", "kurs", "valuta asing", "intervensi"],
    "Inflasi": ["inflasi", "harga pangan", "tekanan harga"],
    "QRIS": ["qris"],
    "BI-FAST": ["bi-fast", "bifast"],
    "Rupiah digital": ["rupiah digital", "proyek garuda", "uang digital"],
    "SRBI/SBN": ["srbi", "sbn", "likuiditas"],
    "Makroprudensial": ["makroprudensial", "ltv", "klm", "kredit umkm", "kredit perbankan"],
    "Pengedaran uang": ["uang palsu", "uang layak edar", "kas keliling", "penukaran uang"],
    "UMKM": ["umkm"],
    "Sistem pembayaran": ["sistem pembayaran", "uang elektronik", "gpn", "kartu kredit"],
}


def policy_tags_for(text: str) -> list[str]:
    hay = text.casefold()
    found = []
    for label, terms in POLICY_GROUPS.items():
        if any(term in hay for term in terms):
            found.append(label)
    return found


def policy_relevance(text: str, category: str = "") -> float:
    """0–100. Semakin banyak kelompok kebijakan yang tersentuh, semakin tinggi."""
    hits = len(policy_tags_for(text))
    bonus = 12 if category in {
        "Kebijakan Moneter",
        "Sistem Pembayaran",
        "Rupiah/Kurs",
        "Inflasi",
        "Perbankan/Kredit",
        "Pengedaran Uang",
    } else 0
    if hits == 0 and bonus == 0:
        return 8.0
    return float(min(100, 18 + hits * 22 + bonus))


def _reach_component(reach: int) -> float:
    # Logaritma supaya satu unggahan viral tidak menelan seluruh skala.
    if reach <= 0:
        return 0.0
    return float(min(100.0, math.log10(reach + 1) / math.log10(5_000_000) * 100))


def score_risk(
    *,
    sentiment: str,
    stance: str,
    reach: int,
    source_tier: int,
    velocity: float,
    has_public_figure: bool,
    credibility: int = 60,
) -> float:
    """Skor risiko reputasi 0–100.

    Komponen:
    - sentimen / stance
    - jangkauan
    - kecepatan penyebaran isu
    - kredibilitas sumber (media arus utama memperbesar risiko bila nadanya negatif)
    - keterlibatan tokoh publik
    """
    cfg = get_config()["weights"]
    if stance == "downside" or sentiment == "negatif":
        sent = 100.0 if stance == "downside" else 80.0
    elif sentiment == "netral" or stance == "netral":
        sent = 45.0
    else:
        sent = 20.0

    tier_weight = {1: 92, 2: 62, 3: 38}.get(source_tier, 50)
    # Sumber tepercaya yang memberitakan sisi positif menekan risiko, bukan menaikkannya.
    if stance == "upside":
        source = 100 - tier_weight
    elif stance == "netral":
        source = 40
    else:
        source = tier_weight
        if credibility >= 75:
            source = min(100, source + 6)

    if has_public_figure and stance == "downside":
        actor = 88.0
    elif has_public_figure:
        actor = 35.0
    else:
        actor = 18.0

    raw = (
        cfg["sentiment"] * sent
        + cfg["reach"] * _reach_component(reach)
        + cfg["velocity"] * max(0.0, min(100.0, velocity))
        + cfg["source"] * source
        + cfg["actor"] * actor
    )
    # Berita baik yang ramai tetap dicatat, tetapi bukan risiko reputasi penuh.
    if stance == "upside":
        raw *= 0.45
    elif stance == "netral":
        raw *= 0.72
    return round(max(0.0, min(100.0, raw)), 1)
