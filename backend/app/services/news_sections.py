"""Klasifikasi rubrik berita untuk beranda DANITA.

Urutan prioritas (paling spesifik dulu) agar tidak tercampur:
  kpw_dki → kpw_provinsi → pemprov_dki → bi_nasional → beranda

Hanya rubrik 2–5 yang memfilter daftar; «Beranda» menampilkan seluruh konten.
"""

from __future__ import annotations

import re

from app.models import Mention

# Salinan daftar provinsi (tanpa impor executive/openpyxl) agar startup ringan di serverless.
PROVINCES = [
    "Kepulauan Riau", "Sumatera Utara", "Sumatera Barat", "Sumatera Selatan",
    "Kalimantan Barat", "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur", "Kalimantan Utara",
    "Sulawesi Utara", "Sulawesi Tengah", "Sulawesi Selatan", "Sulawesi Tenggara", "Sulawesi Barat",
    "Nusa Tenggara Barat", "Nusa Tenggara Timur", "Bangka Belitung", "DI Yogyakarta",
    "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Papua Barat Daya", "Papua Pegunungan",
    "Papua Selatan", "Papua Tengah", "Papua Barat", "Maluku Utara",
    "Aceh", "Riau", "Jambi", "Bengkulu", "Lampung", "Banten", "Bali", "Gorontalo", "Maluku", "Papua",
]

FEED_SECTIONS = ("beranda", "bi_nasional", "kpw_dki", "kpw_provinsi", "pemprov_dki")

FEED_SECTION_LABELS = {
    "beranda": "Beranda",
    "bi_nasional": "Berita Nasional",
    "kpw_dki": "KPwBI DKI Jakarta",
    "kpw_provinsi": "KPwBI",
    "pemprov_dki": "Pemprov DKI Jakarta",
}

BI_POLICY_CATEGORIES = {
    "Kebijakan Moneter",
    "Sistem Pembayaran",
    "Rupiah/Kurs",
    "Inflasi",
    "Perbankan/Kredit",
    "Pengedaran Uang",
    "Reputasi/Kelembagaan",
    "Hoaks/Penipuan",
}

_OTHER_PROVINCES = [p for p in PROVINCES if p != "DKI Jakarta"]

_KPW_MARKERS = re.compile(
    r"\b(?:kpw\s*bi|kpwbi|kantor\s+perwakilan\s+bank\s+indonesia)\b",
    re.I,
)

_KPW_DKI = re.compile(
    r"\b(?:"
    r"kpw\s*bi\s*dki\s*jakarta|"
    r"kpwbi\s+provinsi\s+dki\s+jakarta|"
    r"kpw\s*bi\s*jakarta|"
    r"kpw\s*dki\s*jakarta|"
    r"kpw\s*dki|"
    r"kpwbi\s+dki|"
    r"bank\s+indonesia\s+(?:provinsi\s+)?(?:dki\s+)?jakarta|"
    r"bi\s+jakarta|"
    r"kepala\s+perwakilan\s+bank\s+indonesia\s+provinsi\s+dki\s+jakarta|"
    r"kpw\s+bi\s+provinsi\s+dki"
    r")\b",
    re.I,
)

# Program/agenda KPw DKI — frase lengkap + akronim berkonteks Jakarta/BI.
_KPW_DKI_PROGRAMS = re.compile(
    r"(?:"
    r"\biwan\s+setiawan\b|"
    r"\bjakarta\s+economic\s+forum\b|"
    r"\bperekonomian\s+dki\s+jakarta\b|"
    r"\binflasi\s+tahunan\s+dki\s+jakarta\b|"
    r"\btim\s+pengendalian\s+inflasi\s+daerah\s+jakarta\b|"
    r"\btpid\s+jakarta\b|"
    r"\bkerak\s+telor\s+bi\s+jakarta\b|"
    r"\bumkm\s+dki\s+jakarta\b|"
    r"\bindonesia\s+sharia\s+economic\s+forum\b|"
    r"\bjakarta\s+youth\s+leadership\s+camp\b|"
    r"\bjakarta\s+international\s+investment[,\s]+trade[,\s]+tourism[,\s]+and\s+sme'?s?\s+expo\b|"
    r"\bkuis\s+interaktif\s+tentang\s+literasi(?:\s+bank\s+indonesia\s+jakarta)?\b|"
    r"\bjitex\b|"
    r"\bisef\b|"
    r"\bjef\b"
    r")",
    re.I,
)

_KPW_DKI_HANDLES = (
    "@kpwbi_dki",
    "kpwbi_dki",
    "bankindonesiajakarta",
    "bank indonesia dki",
)

_KPW_OTHER_PROVINCE = [
    re.compile(
        r"\bkpw\s*bi\s+" + re.escape(name) + r"\b",
        re.I,
    )
    for name in sorted(_OTHER_PROVINCES, key=len, reverse=True)
]
_KPW_OTHER_PROVINCE += [
    re.compile(r"\bkpw\s*bi\s+(?:provinsi\s+)?" + re.escape(name) + r"\b", re.I)
    for name in sorted(_OTHER_PROVINCES, key=len, reverse=True)
]

_PEMPROV_DKI = re.compile(
    r"\b(?:"
    r"pemprov\s+(?:dki\s+)?jakarta|"
    r"pemerintah\s+provinsi\s+(?:dki\s+)?jakarta|"
    r"pemprov\s+dki|"
    r"balai\s+kota\s+jakarta|"
    r"diskominfo\s+jakarta|"
    r"satpol\s+pp\s+jakarta|"
    r"bappeda\s+jakarta|"
    r"jakarta\s+smart\s+city|"
    r"jakartasatu|"
    r"dkijakarta"
    r")\b",
    re.I,
)

_PEMPROV_HANDLES = (
    "@dkijakarta",
    "@pemprovdki",
    "jakartagood",
    "dki jakarta official",
)

_BI_NASIONAL = re.compile(
    r"\b(?:"
    r"bank\s+indonesia|"
    r"\bbi\b(?!\s*rate)|"
    r"bi-rate|"
    r"bi\s+7[- ]day|"
    r"suku\s+bunga\s+acuan|"
    r"kebijakan\s+moneter|"
    r"stabilitas\s+(?:nilai\s+tukar|sistem\s+pembayaran)|"
    r"intervensi\s+(?:pasar|valuta)|"
    r"inflasi(?:\s+nasional)?|"
    r"rupiah|"
    r"\bqris\b|"
    r"bi-fast|"
    r"bifast|"
    r"proyek\s+garuda|"
    r"seigniorage|"
    r"reserve\s+requirement|"
    r"gir|rupiah\s+digital|"
    r"money\s+changer|"
    r"pjp|"
    r"penyelenggara\s+sistem\s+pembayaran|"
    r"deputi\s+gubernur\s+bi|"
    r"gubernur\s+bi|"
    r"rdg\s+bi|"
    r"ojk(?=\s+dan\s+bi)|"
    r"mandat\s+bi|"
    r"keuangan\s+daerah|"
    r"kegiatan\s+keuangan\s+daerah"
    r")\b",
    re.I,
)


def classify_feed_section(row: Mention) -> str:
    hay = f"{row.title or ''}\n{row.text or ''}\n{row.source_name or ''}\n{row.author_name or ''}\n{row.author_handle or ''}\n{row.location or ''}"
    folded = hay.casefold()

    if _is_kpw_dki(folded, row):
        return "kpw_dki"
    if _is_kpw_provinsi(folded, row):
        return "kpw_provinsi"
    if _is_pemprov_dki(folded, row):
        return "pemprov_dki"
    if _is_bi_nasional(folded, row):
        return "bi_nasional"
    return "beranda"


_KPW_DKI_NEEDLES = (
    "iwan setiawan",
    "kpwbi",
    "kpw bi",
    "kpw dki",
    "bi jakarta",
    "bank indonesia jakarta",
    "bank indonesia provinsi dki",
    "jakarta economic forum",
    "tpid jakarta",
    "tim pengendalian inflasi daerah jakarta",
    "perekonomian dki jakarta",
    "inflasi tahunan dki",
    "kerak telor",
    "umkm dki jakarta",
    "indonesia sharia economic forum",
    "jakarta youth leadership",
    "jakarta international investment",
    "kuis interaktif tentang literasi",
    "jitex",
    "isef",
    " jef",
)


def row_matches_feed_section(row: Mention, section: str) -> bool:
    """Pakai kolom tersimpan ATAU klasifikasi live — agar rubrik tidak kosong bila retag belum jalan."""
    if not section or section == "beranda":
        return True
    if (getattr(row, "feed_section", None) or "") == section:
        return True
    if classify_feed_section(row) == section:
        return True
    if section == "kpw_dki" and _soft_kpw_dki(row):
        return True
    return False


def _soft_kpw_dki(row: Mention) -> bool:
    """Cadangan longgar: keyword katalog / flag lokal supaya rubrik tidak kosong."""
    hay = f"{row.title or ''} {row.text or ''} {row.location or ''} {row.author_name or ''}".casefold()
    if any(needle in hay for needle in _KPW_DKI_NEEDLES):
        return True
    if row.category in {"Kegiatan KPw DKI", "Ekonomi Jakarta"}:
        return True
    if getattr(row, "is_kpw", False) and ("jakarta" in hay or "dki" in hay):
        return True
    return False


def select_for_feed_section(rows: list, section: str) -> list:
    """Filter rubrik; jika KPw DKI masih kosong, longgarkan ke sinyal Jakarta/KPw."""
    if not section or section == "beranda":
        return list(rows)
    matched = [row for row in rows if row_matches_feed_section(row, section)]
    if matched or section != "kpw_dki":
        return matched
    # Last resort: semua mention yang menyebut Jakarta/DKI dalam jendela.
    loose = []
    for row in rows:
        hay = f"{row.title or ''} {row.text or ''} {row.location or ''}".casefold()
        if "jakarta" in hay or re.search(r"\bdki\b", hay) or getattr(row, "is_kpw", False):
            loose.append(row)
    return loose


def _has_jakarta(folded: str, row: Mention) -> bool:
    if row.location in {
        "Jakarta Pusat", "Jakarta Utara", "Jakarta Barat", "Jakarta Selatan", "Jakarta Timur", "Kepulauan Seribu",
    }:
        return True
    return bool(re.search(r"\b(?:dki\s+)?jakarta\b|\bdki\b", folded))


def _has_bi_signal(folded: str, row: Mention) -> bool:
    if getattr(row, "quotes_bi", False):
        return True
    return bool(
        re.search(
            r"\b(?:bank\s+indonesia|\bbi\b|kpw|qris|bi-rate|bi-fast|tpid|rupiah)\b",
            folded,
        )
    )


def _is_kpw_dki(folded: str, row: Mention) -> bool:
    program_hit = bool(_KPW_DKI_PROGRAMS.search(folded))
    # Akronim pendek (JEF/ISEF/JITEX) hanya jika ada jejak BI/KPw/Jakarta ekonomi.
    if program_hit and re.search(r"\b(?:jef|isef|jitex)\b", folded) and not re.search(
        r"(?:jakarta|bank\s+indonesia|\bbi\b|kpw|ekonomi|umkm|forum|expo|camp)",
        folded,
    ):
        program_hit = False

    explicit = (
        row.category == "Kegiatan KPw DKI"
        or bool(_KPW_DKI.search(folded))
        or program_hit
        or any(handle in folded for handle in _KPW_DKI_HANDLES)
    )
    # Perluas: berita BI/KPw yang menyinggung Jakarta/DKI masuk rubrik KPw DKI
    # (bukan KPw provinsi lain).
    local_bi = (
        _has_jakarta(folded, row)
        and _has_bi_signal(folded, row)
        and not _other_kpw_province_hit(folded)
    )
    ekonomi_jakarta = row.category == "Ekonomi Jakarta" and (
        _has_bi_signal(folded, row) or bool(getattr(row, "is_kpw", False))
    )
    flagged = bool(getattr(row, "is_kpw", False)) and _has_jakarta(folded, row) and _has_bi_signal(folded, row)

    dki_hit = explicit or local_bi or ekonomi_jakarta or flagged
    if not dki_hit:
        return False
    if _other_kpw_province_hit(folded) and not (
        _KPW_DKI.search(folded) or program_hit or row.category == "Kegiatan KPw DKI"
    ):
        return False
    return True


def _other_kpw_province_hit(folded: str) -> bool:
    for pattern in _KPW_OTHER_PROVINCE:
        if pattern.search(folded):
            return True
    for name in _OTHER_PROVINCES:
        if name.casefold() in folded and _KPW_MARKERS.search(folded):
            return True
    return False


def _is_kpw_provinsi(folded: str, row: Mention) -> bool:
    if _is_kpw_dki(folded, row):
        return False
    if not _KPW_MARKERS.search(folded) and "kantor perwakilan" not in folded:
        if not any(name.casefold() in folded for name in _OTHER_PROVINCES):
            return False
    for pattern in _KPW_OTHER_PROVINCE:
        if pattern.search(folded):
            return True
    for name in _OTHER_PROVINCES:
        if name.casefold() in folded and (
            _KPW_MARKERS.search(folded) or "kantor perwakilan bank indonesia" in folded
        ):
            return True
    if re.search(r"\bkpw\s*bi\b", folded, re.I) and _other_kpw_province_hit(folded):
        return True
    return False


def _is_pemprov_dki(folded: str, row: Mention) -> bool:
    if _BI_NASIONAL.search(folded) and not _PEMPROV_DKI.search(folded):
        if not any(h in folded for h in _PEMPROV_HANDLES):
            return False
    if _PEMPROV_DKI.search(folded):
        return True
    if any(h in folded for h in _PEMPROV_HANDLES):
        return True
    if re.search(r"\b(?:gubernur|wagub)\s+(?:dki\s+)?jakarta\b", folded) and "bank indonesia" not in folded:
        return True
    if row.category == "Ekonomi Jakarta" and _PEMPROV_DKI.search(folded):
        return True
    if row.category == "Ekonomi Jakarta" and not _BI_NASIONAL.search(folded):
        if re.search(r"\b(?:pemprov|pemda|dinas\s+|jakarta\s+pintu)\b", folded):
            return True
    return False


def _is_bi_nasional(folded: str, row: Mention) -> bool:
    if row.quotes_bi:
        return True
    if row.category in BI_POLICY_CATEGORIES:
        return True
    if _BI_NASIONAL.search(folded):
        return True
    return False
