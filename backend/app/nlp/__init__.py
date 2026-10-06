"""Klasifikasi sentimen dan upside/downside untuk bahasa Indonesia.

Ini mesin leksikon + aturan, bukan model saraf. Hasilnya cukup untuk uji
alur kerja dan contoh data. Antarmuka `analyze()` jangan diubah bila tim
menggantinya dengan IndoBERT atau LLM: isi objek hasil yang sama.

Koreksi manusia disimpan di tabel audit dan kolom human_corrected.
Pada tahap berikutnya, kumpulan koreksi itu menjadi data latih.
"""

from __future__ import annotations

import re

from app.constants import CATEGORIES
from app.nlp.config_store import get_config
from app.nlp.risk import policy_relevance, policy_tags_for, score_risk

# Dipetakan ke bentuk baku sebelum dihitung, agar "gak stabil" terbaca "tidak stabil".
SLANG = {
    "gak": "tidak",
    "ga": "tidak",
    "nggak": "tidak",
    "ngga": "tidak",
    "tdk": "tidak",
    "yg": "yang",
    "dgn": "dengan",
    "krn": "karena",
    "karna": "karena",
    "bgt": "sekali",
    "bener": "benar",
    "udah": "sudah",
    "udh": "sudah",
    "sdh": "sudah",
    "blm": "belum",
    "aja": "saja",
    "kalo": "kalau",
    "trs": "terus",
    "jg": "juga",
    "dr": "dari",
    "utk": "untuk",
    "org": "orang",
    "sy": "saya",
    "nyungsep": "anjlok",
    "jeblok": "anjlok",
    "ambruk": "anjlok",
}

POSITIVE = {
    "apresiasi", "berhasil", "meningkat", "menguat", "stabil", "terkendali",
    "dipercaya", "kepercayaan", "inovasi", "memudahkan", "transparan",
    "transparansi", "penghargaan", "positif", "optimistis", "pulih",
    "tumbuh", "aman", "lancar", "tepat", "dukungan", "terbantu", "edukasi",
    "klarifikasi", "resmi", "peluang", "perluasan", "mudah", "cepat",
    "apresiatif", "kredibel", "tertib", "meluas", "manfaat",
}

NEGATIVE = {
    "hoaks", "penipuan", "tipu", "phishing", "kritik", "kritis", "melemah",
    "anjlok", "turun", "gagal", "gangguan", "lumpuh", "bocor", "kebocoran",
    "demo", "protes", "keluhan", "kontroversi", "khawatir", "panik",
    "rugi", "merugi", "lambat", "error", "tidak", "bukan", "buruk",
    "memburuk", "tekanan", "risiko", "ancaman", "bohong", "palsu",
    "mengeluh", "kecewa", "marah", "berat",
}

# "tidak" dan "bukan" hanya berarti negatif bila menempel pada kata positif.
NEGATIONS = {"tidak", "bukan", "tanpa", "belum"}

SARCASM_CUES = [
    "makasih ya",
    "terima kasih ya",
    "mantap sekali",
    "bagus banget ya",
    "alhamdulillah",
    "yeah right",
]

CATEGORY_TERMS: list[tuple[str, list[str]]] = [
    ("Hoaks/Penipuan", ["hoaks", "penipuan", "phishing", "modus", "tipu", "mengatasnamakan"]),
    ("Kegiatan KPw DKI", ["kpw bi", "kpw dki", "kantor perwakilan", "kas keliling", "kpwbi"]),
    ("Ekonomi Jakarta", ["jakarta", "tpid", "harga pangan", "dki"]),
    ("Sistem Pembayaran", ["qris", "bi-fast", "bifast", "rupiah digital", "proyek garuda", "gpn", "uang elektronik"]),
    ("Rupiah/Kurs", ["rupiah", "nilai tukar", "kurs", "valuta asing", "dolar"]),
    ("Inflasi", ["inflasi", "harga pangan", "tekanan harga"]),
    ("Kebijakan Moneter", ["bi-rate", "suku bunga", "rdg", "rapat dewan gubernur", "kebijakan moneter"]),
    ("Perbankan/Kredit", ["kredit", "perbankan", "ltv", "klm", "kpr", "bunga kredit"]),
    ("Pengedaran Uang", ["uang palsu", "uang layak edar", "penukaran uang", "uang baru"]),
    ("Reputasi/Kelembagaan", ["independensi", "burden sharing", "kritik", "reputasi", "kepercayaan"]),
]


def normalize(text: str) -> str:
    raw = text.casefold()
    raw = raw.replace("bi fast", "bi-fast").replace("birate", "bi-rate")
    tokens = re.findall(r"[a-z0-9@#-]+", raw, flags=re.IGNORECASE)
    mapped = [SLANG.get(token, token) for token in tokens]
    return " ".join(mapped)


def _hits(words: list[str], lexicon: set[str]) -> list[str]:
    found = []
    for index, word in enumerate(words):
        if word not in lexicon:
            continue
        negated = index > 0 and words[index - 1] in NEGATIONS
        # "tidak" sendiri ada di lexicon negatif; jangan dihitung ganda sebagai kata isi.
        if word in NEGATIONS:
            continue
        if negated:
            found.append(f"!{word}")
        else:
            found.append(word)
    return found


def _score_lexicon(words: list[str]) -> tuple[float, list[str], list[str]]:
    pos = _hits(words, POSITIVE)
    neg = _hits(words, NEGATIVE)
    pos_n = sum(1 if not item.startswith("!") else -1 for item in pos)
    neg_n = sum(1 if not item.startswith("!") else -1 for item in neg)
    # "bukan hoaks": hoaks terkena negasi, jadi tidak menambah skor negatif.
    total = pos_n + neg_n
    if total == 0 and pos_n == 0 and neg_n == 0:
        return 0.0, pos, neg
    score = (pos_n - neg_n) / max(3, abs(pos_n) + abs(neg_n) + 1)
    return max(-1.0, min(1.0, score)), pos, neg


def _category(text: str) -> str:
    best = "Lainnya"
    best_n = 0
    for name, terms in CATEGORY_TERMS:
        count = sum(1 for term in terms if term in text)
        if count > best_n:
            best = name
            best_n = count
    return best if best in CATEGORIES else "Lainnya"


def _rationale(sentiment: str, stance: str, pos: list[str], neg: list[str], sarcasm: bool, category: str) -> str:
    bits = []
    shown_pos = [item.lstrip("!") for item in pos if not item.startswith("!")][:3]
    shown_neg = [item.lstrip("!") for item in neg if not item.startswith("!")][:3]
    if shown_neg:
        bits.append("sinyal negatif: " + ", ".join(shown_neg))
    if shown_pos:
        bits.append("sinyal positif: " + ", ".join(shown_pos))
    if sarcasm:
        bits.append("ada pola yang mirip sarkasme sehingga nada dibalik dan keyakinan diturunkan")
    if not bits:
        bits.append("tidak ada kata bernada kuat, sehingga dikelompokkan netral")
    stance_label = {"upside": "Upside", "downside": "Downside", "netral": "Netral"}[stance]
    return (
        f"Diklasifikasikan {stance_label} ({sentiment}) karena "
        + "; ".join(bits)
        + f". Subkategori: {category}."
    )


def analyze(
    text: str,
    *,
    reach: int = 0,
    source_tier: int = 2,
    velocity: float = 30,
    has_public_figure: bool = False,
    credibility: int = 60,
) -> dict:
    """Klasifikasikan satu teks. Parameter jangkauan hanya mempengaruhi skor risiko."""
    normalized = normalize(text)
    words = normalized.split()
    score, pos, neg = _score_lexicon(words)
    sarcasm = any(cue in normalized for cue in SARCASM_CUES) and any(
        word in normalized for word in ("anjlok", "melemah", "rugi", "gangguan", "hoaks", "lambat")
    )
    if sarcasm and score > -0.2:
        score = min(score, -0.35)

    thresholds = get_config()["thresholds"]
    if score >= thresholds["positive"]:
        sentiment = "positif"
    elif score <= thresholds["negative"]:
        sentiment = "negatif"
    else:
        sentiment = "netral"

    # "bukan hoaks" tidak dihitung sebagai isu hoaks: kata sensitif yang didahului negasi diabaikan.
    sensitive_words = {"hoaks", "penipuan", "kebocoran", "phishing", "demo"}
    sensitive = any(
        word in sensitive_words and not (index > 0 and words[index - 1] in NEGATIONS)
        for index, word in enumerate(words)
    )
    if sensitive and sentiment != "positif":
        stance = "downside"
        sentiment = "negatif" if score < 0.2 else sentiment
    elif sentiment == "positif":
        stance = "upside"
    elif sentiment == "negatif":
        stance = "downside"
    else:
        stance = "netral"

    margin = abs(score)
    confidence = min(0.93, 0.46 + margin)
    if sarcasm:
        confidence = min(confidence, 0.58)
    if sentiment == "netral":
        confidence = min(confidence, 0.64)

    category = _category(normalized)
    tags = policy_tags_for(normalized)
    relevance = policy_relevance(normalized, category)
    risk = score_risk(
        sentiment=sentiment,
        stance=stance,
        reach=reach,
        source_tier=source_tier,
        velocity=velocity,
        has_public_figure=has_public_figure,
        credibility=credibility,
    )
    return {
        "sentiment": sentiment,
        "sentiment_score": round(score, 3),
        "stance": stance,
        "confidence": round(confidence, 2),
        "rationale": _rationale(sentiment, stance, pos, neg, sarcasm, category),
        "category": category,
        "policy_tags": tags,
        "policy_relevance": round(relevance, 1),
        "risk_score": risk,
        "normalized_text": normalized,
    }
