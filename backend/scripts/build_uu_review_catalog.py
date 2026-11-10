#!/usr/bin/env python3
"""Ekstrak cuplikan Pasal dari PDF UU di root repo → backend/app/data/uu_review_catalog.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("Install pypdf", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "uu_review_catalog.json"

UU_FILES = {
    "UU_NO_20_2016_REV-JAN26_KNS.pdf": (20, 2016, "Merek dan Indikasi Geografis"),
    "UU_NO_28_2014_REV-JAN26_KNSUM (1).pdf": (28, 2014, "Hak Cipta"),
    "UU_NO_31_2000_KNS.pdf": (31, 2000, "Desain Tata Uang Rupiah"),
    "UU_NO_13_2016_REV-SEP26_KNSUM.pdf": (13, 2016, "Hukum Acara Perdata"),
    "UU BI.pdf": (23, 1999, "Bank Indonesia"),
    "UU PDP.pdf": (27, 2022, "Pelindungan Data Pribadi"),
    "UU KIP.pdf": (14, 2008, "Keterbukaan Informasi Publik"),
    "UU P2SK.pdf": (4, 2023, "Pengembangan dan Penguatan Sektor Keuangan"),
    "UU Administrasi Pemerintahan.pdf": (30, 2014, "Administrasi Pemerintahan"),
    "UU Pembentukan Peraturan Perundang-Undangan.pdf": (12, 2011, "Pembentukan Peraturan Perundang-Undangan"),
    "UU Perjanjian Internasional.pdf": (24, 2000, "Perjanjian Internasional"),
}

PAGE_LIMIT = {"UU P2SK.pdf": 90, "UU_NO_13_2016_REV-SEP26_KNSUM.pdf": 80}

THEMES = {
    "Merek dan Indikasi Geografis": {
        "tema": ["merek", "indikasi geografis", "pendaftaran merek", "pelanggaran merek", "meniru", "duplikasi"],
        "larangan_bahasa": r"duplikasi|meniru|menyalin|memalsukan|menggunakan merek terdaftar",
        "cocok_bahasa": r"merek|indikasi geografis|pendaftaran|DJKI|HAKI",
    },
    "Hak Cipta": {
        "tema": ["hak cipta", "reproduksi", "royalti", "plagiat", "lisensi"],
        "larangan_bahasa": r"plagiat|menyalin karya|unggah tanpa izin|pirated",
        "cocok_bahasa": r"hak cipta|pencipta|lisensi|royalti",
    },
    "Desain Tata Uang Rupiah": {
        "tema": ["pengedaran rupiah", "pemalsuan uang", "desain uang"],
        "larangan_bahasa": r"memalsu uang|uang palsu|cetak uang|mencetak rupiah",
        "cocok_bahasa": r"rupiah|pengedaran|desain",
    },
    "Pelindungan Data Pribadi": {
        "tema": ["data pribadi", "persetujuan", "pemrosesan", "kebocoran"],
        "larangan_bahasa": r"sebar NIK|bocorkan data|tanpa persetujuan|jual data pribadi",
        "cocok_bahasa": r"data pribadi|privasi|persetujuan",
    },
    "Bank Indonesia": {
        "tema": ["kebijakan moneter", "nilai tukar", "sistem pembayaran", "rupiah", "BI-Rate"],
        "larangan_bahasa": r"sinyal suku bunga|prakiraan BI-Rate|menjamin profit|mencetak uang untuk rakyat",
        "cocok_bahasa": r"Bank Indonesia|stabilitas|moneter",
    },
    "Keterbukaan Informasi Publik": {
        "tema": ["informasi publik", "dikecualikan", "rahasia", "embargo"],
        "larangan_bahasa": r"rahasia negara|off the record|belum boleh diumumkan",
        "cocok_bahasa": r"informasi publik|keterbukaan|akses informasi",
    },
}


def clean(text: str) -> str:
    text = re.sub(r"[\u200b-\u200f\uFEFF]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_pasals(text: str, limit: int = 120) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"Pasal\s+(\d+)\b", text):
        if len(out) >= limit:
            break
        pasal = m.group(1)
        if pasal in out:
            continue
        start = m.start()
        nxt = re.search(r"Pasal\s+\d+\b", text[m.end() :])
        end = m.end() + nxt.start() if nxt else min(len(text), start + 900)
        out[pasal] = clean(text[start:end])[:450]
    return out


def main() -> None:
    catalog: dict = {}
    for fname, (num, year, judul) in UU_FILES.items():
        pdf = ROOT / fname
        if not pdf.exists():
            continue
        reader = PdfReader(str(pdf))
        max_pages = PAGE_LIMIT.get(fname, len(reader.pages))
        text = ""
        for page in reader.pages[:max_pages]:
            text += (page.extract_text() or "") + "\n"
        text = clean(text)
        pasals = extract_pasals(text)
        nums = [int(p) for p in pasals]
        theme = THEMES.get(judul, {})
        catalog[f"{num}/{year}"] = {
            "nomor": num,
            "tahun": year,
            "judul": judul,
            "label_resmi": f"UU No. {num} Tahun {year} tentang {judul}",
            "sumber_file": fname,
            "pasal_max_ekstrak": max(nums) if nums else 0,
            "tema_prioritas": theme.get("tema", []),
            "larangan_bahasa": theme.get("larangan_bahasa", ""),
            "cocok_bahasa": theme.get("cocok_bahasa", ""),
            "pasal_cuplikan": pasals,
        }
        print(f"OK {fname}: {len(pasals)} pasal, max={max(nums) if nums else 0}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
