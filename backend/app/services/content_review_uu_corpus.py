"""Memuat katalog UU hasil ekstraksi PDF (folder root repo) untuk Review Konten."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "uu_review_catalog.json"
_CATALOG_VERSION = "uu-corpus-1"

# Implikasi operasional per UU (diselaraskan dengan PDF yang diunggah pengguna).
CORPUS_IMPLIKASI = [
    {
        "uu": (20, 2016),
        "pola": re.compile(
            r"\b(duplikasi|menduplikasi|meniru|menyalin|memalsukan)\s+merek\b|"
            r"\bmerek\s+terdaftar\b.*\b(tiru|salin|duplikasi)\b|"
            r"\bmemalsukan\s+indikasi\s+geografis\b",
            re.I | re.S,
        ),
        "risiko": "Tinggi",
        "masalah": "Konten menganjurkan atau membenarkan peniruan merek/indikasi geografis.",
        "saran": "Kami mengimbau UMKM mendaftarkan merek sendiri secara resmi dan tidak meniru merek atau IG terdaftar milik pihak lain.",
        "alasan": "UU No. 20 Tahun 2016 melindungi merek terdaftar; anjuran peniruan berisiko pidana dan perdata.",
    },
    {
        "uu": (28, 2014),
        "pola": re.compile(
            r"\b(plagiat|membajak|bajakan)\b|"
            r"\b(unggah|upload|share)\b.{0,40}\b(tanpa izin|tanpa hak)\b.{0,40}\b(karya|lagu|foto|video)\b|"
            r"\bsalinan\b.{0,30}\b(hak cipta|karya)\b",
            re.I | re.S,
        ),
        "risiko": "Tinggi",
        "masalah": "Draf mengindikasikan penggunaan karya tanpa izin pemegang hak cipta.",
        "saran": "Gunakan karya berlisensi atau milik BI; cantumkan kredit dan izin tertulis bila memakai karya pihak ketiga.",
        "alasan": "UU No. 28 Tahun 2014 mengatur hak ekonomi dan larangan Penggandaan tanpa izin.",
    },
    {
        "uu": (31, 2000),
        "pola": re.compile(
            r"\b(uang palsu|memalsu uang|mencetak rupiah|rupiah palsu|desain uang tiruan)\b",
            re.I,
        ),
        "risiko": "Tinggi",
        "masalah": "Bahasa terkait pemalsuan uang rupiah.",
        "saran": "Hapus narasi pemalsuan; edukasi ciri keaslian uang sesuai rilis BI.",
        "alasan": "UU No. 31 Tahun 2000 mengatur desain dan pengedaran uang; pemalsuan adalah kejahatan.",
    },
    {
        "uu": (27, 2022),
        "pola": re.compile(
            r"\b(bocorkan|jual|sebar|unggah).{0,50}\b(data pribadi|NIK|rekening|alamat)\b|"
            r"\btanpa persetujuan\b.{0,40}\b(data pribadi)\b",
            re.I | re.S,
        ),
        "risiko": "Tinggi",
        "masalah": "Draf dapat menormalkan penyimpanan atau penyebaran data pribadi tanpa dasar hukum.",
        "saran": "Hapus data pribadi contoh nyata; gunakan ilustrasi dan rujuk kebijakan privasi resmi.",
        "alasan": "UU No. 27 Tahun 2022 mensyaratkan dasar dan persetujuan pemrosesan data pribadi.",
    },
    {
        "uu": (23, 1999),
        "pola": re.compile(
            r"\b(BI|Bank Indonesia)\s+(menerbitkan|membagikan|mencetak)\s+uang\s+tunai\s+untuk\b|"
            r"\bbukan\s+wewenang\s+BI\b.*\b(tetap|tetapi)\s+dilakukan\b",
            re.I | re.S,
        ),
        "risiko": "Tinggi",
        "masalah": "Narasi bertentangan dengan mandat dan wewenang Bank Indonesia.",
        "saran": "Selaraskan dengan fungsi bank sentral yang diumumkan resmi (moneter, pembayaran, pengedaran).",
        "alasan": "UU No. 23 Tahun 1999 mengatur mandat BI; komunikasi tidak boleh menyimpangkan fungsi.",
    },
    {
        "uu": (14, 2008),
        "pola": re.compile(
            r"\b(informasi rahasia|dikecualikan)\b.{0,50}\b(wajib|harus)\s+diumumkan\b|"
            r"\bbuka\s+data\s+internal\b.{0,30}\b(publik|media)\b",
            re.I | re.S,
        ),
        "risiko": "Sedang",
        "masalah": "Bahasa dapat menyesatkan tentang kewajiban keterbukaan informasi publik.",
        "saran": "Jelaskan hanya informasi yang memang klasifikasi publik; rujuk pengecualian resmi KIP.",
        "alasan": "UU No. 14 Tahun 2008 membatasi jenis informasi yang wajib dibuka.",
    },
    {
        "uu": (12, 2011),
        "pola": re.compile(
            r"\b(undang-undang)\s+(sudah|telah)\s+ditetapkan\b.{0,30}\b(tanpa|belum)\s+(DPR|prosedur)\b",
            re.I | re.S,
        ),
        "risiko": "Sedang",
        "masalah": "Pernyataan tentang pembentukan peraturan tanpa konteks prosedur yang benar.",
        "saran": "Hindari klaim pembentukan UU; rujuk peraturan yang sudah terbit resmi.",
        "alasan": "UU No. 12 Tahun 2011 mengatur mekanisme pembentukan peraturan.",
    },
]


def catalog_version() -> str:
    return _CATALOG_VERSION


def load_catalog() -> dict:
    if not _CATALOG_PATH.is_file():
        return {}
    try:
        return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def uu_label(num: int, year: int) -> str:
    key = f"{num}/{year}"
    entry = load_catalog().get(key)
    if entry:
        return entry.get("label_resmi") or f"UU No. {num} Tahun {year} tentang {entry.get('judul', '')}"
    return f"UU No. {num} Tahun {year}"


def pasal_max_from_corpus(num: int, year: int) -> int | None:
    key = f"{num}/{year}"
    entry = load_catalog().get(key)
    if not entry:
        return None
    return (
        entry.get("pasal_max_ekstrak")
        or entry.get("pasal_max")
        or None
    )


def corpus_sources_line() -> str:
    cat = load_catalog()
    if not cat:
        return ""
    names = sorted({v.get("sumber_file", "") for v in cat.values() if v.get("sumber_file")})
    return f"{len(cat)} UU dari berkas: " + ", ".join(names[:4]) + ("…" if len(names) > 4 else "")


def pasal_snippet(num: int, year: int, pasal: int) -> str:
    key = f"{num}/{year}"
    entry = load_catalog().get(key)
    if not entry:
        return ""
    snippets = entry.get("pasal_cuplikan") or entry.get("pasal") or {}
    raw = snippets.get(str(pasal)) or ""
    raw = re.sub(r"TRAINEE INTERNSHIP.*?(?=Pasal|$)", " ", raw, flags=re.I)
    raw = re.sub(r"www\.hukumonline\.com\S*", "", raw)
    return re.sub(r"\s+", " ", raw).strip()[:220]


def _sentence_bounds(text: str, index: int) -> tuple[int, int]:
    start = max(text.rfind(".", 0, index), text.rfind("!", 0, index), text.rfind("\n", 0, index))
    start = 0 if start < 0 else start + 1
    ends = [text.find(m, index) for m in ".!?\n"]
    ends = [e for e in ends if e >= 0]
    end = (min(ends) + 1) if ends else len(text)
    return start, end


def analyze_corpus(text: str, make_finding: Callable[..., dict]) -> list[dict]:
    findings: list[dict] = []
    for rule in CORPUS_IMPLIKASI:
        num, year = rule["uu"]
        legal = f"{uu_label(num, year)}. Perlu verifikasi tim Hukum."
        for match in rule["pola"].finditer(text):
            span_start, span_end = match.start(), match.end()
            s_start, s_end = _sentence_bounds(text, span_start)
            sentence = text[s_start:s_end].strip()
            findings.append(
                make_finding(
                    s_start,
                    s_end,
                    sentence,
                    "implikasi_hukum",
                    rule["risiko"],
                    f"[Korpus UU] {rule['masalah']}",
                    legal,
                    rule["saran"],
                    rule["alasan"],
                    span_start=span_start,
                    span_end=span_end,
                    hapus=text[span_start:span_end],
                    tambah=None,
                )
            )
    return findings


def enrich_pasal_problem(num: int, year: int, pasal: int) -> str:
    snip = pasal_snippet(num, year, pasal)
    if snip:
        return f"Cuplikan korpus Pasal {pasal}: «{snip[:180]}…» (verifikasi Unit Hukum)."
    return ""
