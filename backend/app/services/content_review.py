"""Pemeriksa draf siaran pers dan caption.

Tanpa LLM_API_KEY, temuan berasal dari aturan kata. Nomor pasal tidak
ditulis. Nama peraturan disertai catatan verifikasi tim Hukum.
Jika kunci ada, model boleh menambah temuan, tetapi setiap "Pasal N"
diganti menjadi catatan verifikasi.
"""

from __future__ import annotations

import json
import os
import re
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.services.dss_llm import _complete, _parse_json

DISCLAIMER = (
    "Hasil review adalah alat bantu AI dan tidak menggantikan review resmi "
    "oleh Unit Hukum/Kepatuhan."
)
RULES = [
    (
        re.compile(r"\b\d{16}\b"),
        "regulasi",
        "Tinggi",
        "Ada deret 16 digit yang menyerupai nomor identitas.",
        "UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Hapus nomor identitas dari draf publik.",
        "Data yang dapat mengidentifikasi seseorang tidak perlu tampil di siaran atau caption.",
    ),
    (
        re.compile(r"[\w.+-]+@[\w.-]+\.\w+"),
        "regulasi",
        "Sedang",
        "Ada alamat surel pribadi atau internal di dalam draf.",
        "UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Ganti dengan kanal resmi kantor, bukan surel perorangan.",
        "Surel perorangan dapat menjadi data pribadi bila menunjuk orang tertentu.",
    ),
    (
        re.compile(r"\b(\+62|08)\d{8,12}\b"),
        "regulasi",
        "Sedang",
        "Ada nomor telepon di dalam draf.",
        "UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Gunakan nomor layanan resmi yang memang boleh diumumkan, atau hapus nomor ini.",
        "Nomor telepon pribadi tidak perlu ikut tersebar bersama materi publik.",
    ),
    (
        re.compile(r"\b(dipastikan|pasti akan|akan menurunkan suku bunga|akan menaikkan suku bunga|sinyal pelonggaran|sinyal pengetatan)\b", re.I),
        "reputasi",
        "Tinggi",
        "Kalimat ini dapat dibaca sebagai sinyal kebijakan yang belum menjadi pengumuman resmi.",
        "UU No. 23 Tahun 1999 tentang Bank Indonesia sebagaimana diubah, termasuk melalui UU No. 4 Tahun 2023 tentang P2SK. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Ganti dengan kalimat yang mengutip keputusan yang sudah diumumkan, atau hapus prakiraan arah kebijakan.",
        "Prakiraan arah suku bunga dari kehumasan dapat menggerakkan persepsi pasar.",
    ),
    (
        re.compile(r"\b(terbaik|satu-satunya|dijamin untung|paling aman|tanpa risiko)\b", re.I),
        "regulasi",
        "Sedang",
        "Ada klaim mutlak yang dapat dibaca sebagai informasi yang tidak seimbang.",
        "UU No. 8 Tahun 1999 tentang Perlindungan Konsumen. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Sebut fakta yang terukur dan sumbernya, tanpa kata mutlak.",
        "Klaim mutlak mudah disalahpahami sebagai janji.",
    ),
    (
        re.compile(r"\b(gambar|foto|ilustrasi)\s+(dari|milik|karya)\b", re.I),
        "regulasi",
        "Sedang",
        "Materi visual pihak lain disebut tanpa keterangan izin yang jelas.",
        "UU No. 28 Tahun 2014 tentang Hak Cipta. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Gunakan materi milik BI atau tulis izin dan kredit yang sudah dicek.",
        "Materi pihak lain tidak boleh ikut terbit hanya karena sudah ada di internet.",
    ),
    (
        re.compile(r"\b(rahasia|embargo|belum boleh diumumkan|off the record)\b", re.I),
        "regulasi",
        "Tinggi",
        "Draf memuat penanda informasi yang mungkin belum boleh dibuka.",
        "UU No. 14 Tahun 2008 tentang Keterbukaan Informasi Publik. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Keluarkan kalimat ini dari versi publik.",
        "Penanda embargo atau rahasia tidak boleh ikut pada naskah yang akan diunggah.",
    ),
]


def review(text: str, kind: str = "siaran", platform: str = "") -> dict:
    original = (text or "").strip()
    if len(original) < 20:
        return _empty("Teks terlalu pendek untuk ditinjau.")
    findings = []
    for chunk_start, chunk in _chunks(original):
        findings.extend(_rules(chunk, chunk_start))
        findings.extend(_style(chunk, chunk_start, kind, platform))
    findings.extend(_llm(original, findings))
    findings = _dedupe(findings)
    revised = apply_all(original, findings)
    score, status = _score(findings)
    return {
        "disclaimer": DISCLAIMER,
        "kind": kind,
        "platform": platform,
        "original": original,
        "revised": revised,
        "findings": findings,
        "score": score,
        "status": status,
        "counts": _counts(findings),
        "method": "aturan" if not os.environ.get("LLM_API_KEY", "").strip() else "aturan+model",
    }


def apply_all(original: str, findings: list[dict]) -> str:
    accepted = [item for item in findings if item.get("accepted", True) and item.get("saran")]
    accepted.sort(key=lambda item: item["start"], reverse=True)
    text = original
    for item in accepted:
        start, end = item["start"], item["end"]
        if 0 <= start < end <= len(text):
            text = text[:start] + item["saran"] + text[end:]
    return text


def docx_bytes(original: str, revised: str, findings: list[dict], score: int, status: str) -> bytes:
    lines = [
        "Review Konten Danita",
        DISCLAIMER,
        f"Skor kesiapan publikasi: {score}",
        f"Status: {status}",
        "",
        "Versi revisi",
        revised,
        "",
        "Temuan",
    ]
    for item in findings:
        lines.append(f"- [{item.get('risiko')}] {item.get('masalah')}")
        lines.append(f"  Saran: {item.get('saran')}")
        lines.append(f"  Alasan: {item.get('alasan')}")
        lines.append(f"  Dasar: {item.get('dasar_hukum')}")
    lines.extend(["", "Versi asli", original])
    document = _document_xml(lines)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def _rules(chunk: str, offset: int) -> list[dict]:
    found = []
    for pattern, category, risk, problem, legal, suggestion, reason in RULES:
        for match in pattern.finditer(chunk):
            start = offset + match.start()
            end = offset + _sentence_end(chunk, match.end())
            sentence_start = offset + _sentence_start(chunk, match.start())
            sentence = chunk[_sentence_start(chunk, match.start()):_sentence_end(chunk, match.end())].strip()
            found.append(_finding(sentence_start, end, sentence, category, risk, problem, legal, suggestion, reason))
    return found


def _style(chunk: str, offset: int, kind: str, platform: str) -> list[dict]:
    found = []
    for match in re.finditer(r"[^.!?\n]+[.!?]?", chunk):
        sentence = match.group().strip()
        if not sentence:
            continue
        words = sentence.split()
        start = offset + match.start()
        end = offset + match.end()
        if len(words) > 45:
            found.append(_finding(
                start, end, sentence, "ambigu", "Sedang",
                "Kalimat lebih dari 45 kata dan sulit diikuti dalam sekali baca.",
                "Pedoman komunikasi yang jelas. Bukan pasal undang-undang. Perlu verifikasi tim Hukum bila menyangkut substansi.",
                _shorten(sentence),
                "Kalimat yang lebih pendek mengurangi tafsir ganda.",
            ))
        if re.search(r"\d", sentence) and not re.search(r"\b(20\d\d|periode|per |hingga|sampai|tahun|bulan)\b", sentence, re.I):
            found.append(_finding(
                start, end, sentence, "ambigu", "Sedang",
                "Ada angka tanpa periode atau sumber yang tertulis pada kalimat yang sama.",
                "UU No. 8 Tahun 1999 tentang Perlindungan Konsumen. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
                sentence.rstrip(".!?") + " (sebutkan periode dan sumber data).",
                "Angka tanpa periode mudah dibaca di luar konteks.",
            ))
        if re.search(r"\b(gue|lo|gw|wkwk|anjir)\b", sentence, re.I):
            found.append(_finding(
                start, end, sentence, "gaya", "Rendah",
                "Ada kata tidak baku untuk kanal resmi.",
                "Pedoman bahasa Indonesia. Bukan pasal undang-undang.",
                "Tulis ulang dengan kata baku dan sapaan resmi.",
                "Kanal Bank Indonesia memakai ragam formal.",
            ))
        if kind == "caption" and platform in {"X", "Twitter"} and len(sentence) > 240:
            found.append(_finding(
                start, end, sentence, "gaya", "Rendah",
                "Caption untuk X lebih panjang dari 240 karakter.",
                "Batasan praktis platform, bukan peraturan perundang-undangan.",
                sentence[:220].rstrip() + "…",
                "Caption yang terpotong otomatis kehilangan ujung kalimat.",
            ))
    return found


def _llm(original: str, existing: list[dict]) -> list[dict]:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return []
    system = (
        "Anda reviewer komunikasi bank sentral. Balas JSON {\"findings\": [...]} . "
        "Setiap temuan punya kalimat, kategori (ambigu|regulasi|gaya|reputasi), risiko (Tinggi|Sedang|Rendah), "
        "masalah, dasar_hukum, saran, alasan. Jangan menulis nomor pasal. "
        "Jika ragu, tulis nama peraturan dan kalimat 'Perlu verifikasi tim Hukum'. "
        "Jangan menambah fakta yang tidak ada di draf."
    )
    raw = _complete(system, original[:6000], key)
    parsed = _parse_json(raw or "")
    if not parsed:
        return []
    extra = []
    for item in parsed.get("findings") or []:
        if not isinstance(item, dict):
            continue
        sentence = str(item.get("kalimat") or item.get("sentence") or "").strip()
        if not sentence or sentence not in original:
            continue
        start = original.find(sentence)
        legal = _no_pasal(str(item.get("dasar_hukum") or "Perlu verifikasi tim Hukum."))
        extra.append(_finding(
            start,
            start + len(sentence),
            sentence,
            str(item.get("kategori") or "ambigu"),
            str(item.get("risiko") or "Sedang"),
            _no_pasal(str(item.get("masalah") or "")),
            legal,
            _no_pasal(str(item.get("saran") or sentence)),
            _no_pasal(str(item.get("alasan") or "")),
        ))
    return extra


def _finding(start, end, sentence, category, risk, problem, legal, suggestion, reason) -> dict:
    return {
        "start": start,
        "end": end,
        "kalimat": sentence,
        "kategori": category if category in {"ambigu", "regulasi", "gaya", "reputasi"} else "ambigu",
        "risiko": risk if risk in {"Tinggi", "Sedang", "Rendah"} else "Sedang",
        "masalah": problem,
        "dasar_hukum": _no_pasal(legal),
        "saran": suggestion,
        "alasan": reason,
        "accepted": True,
    }


def _no_pasal(text: str) -> str:
    cleaned = re.sub(r"Pasal\s+\d+[A-Za-z]?(?:\s+ayat\s*\(\d+\))?", "ketentuan terkait", text)
    if "verifikasi" not in cleaned.lower() and "undang" in cleaned.lower():
        cleaned = cleaned.rstrip(".") + ". Perlu verifikasi tim Hukum."
    return cleaned


def _chunks(text: str):
    if len(text) <= 3500:
        return [(0, text)]
    parts = []
    cursor = 0
    while cursor < len(text):
        end = min(len(text), cursor + 3500)
        if end < len(text):
            cut = text.rfind("\n", cursor, end)
            if cut > cursor:
                end = cut
        parts.append((cursor, text[cursor:end]))
        cursor = end
    return parts


def _sentence_start(chunk: str, index: int) -> int:
    prev = max(chunk.rfind(".", 0, index), chunk.rfind("!", 0, index), chunk.rfind("?", 0, index), chunk.rfind("\n", 0, index))
    return 0 if prev < 0 else prev + 1


def _sentence_end(chunk: str, index: int) -> int:
    candidates = [chunk.find(mark, index) for mark in ".!?\n"]
    candidates = [item for item in candidates if item >= 0]
    return (min(candidates) + 1) if candidates else len(chunk)


def _shorten(sentence: str) -> str:
    words = sentence.split()
    return " ".join(words[:28]).rstrip(".,") + "."


def _dedupe(findings: list[dict]) -> list[dict]:
    seen = set()
    kept = []
    for item in findings:
        key = (item["start"], item["kategori"], item["masalah"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    kept.sort(key=lambda item: item["start"])
    return kept


def _score(findings: list[dict]) -> tuple[int, str]:
    penalty = {"Tinggi": 25, "Sedang": 10, "Rendah": 4}
    score = 100
    high = False
    for item in findings:
        score -= penalty.get(item["risiko"], 10)
        high = high or item["risiko"] == "Tinggi"
    score = max(0, score)
    if high or score < 60:
        status = "Berisiko Tinggi"
    elif score < 85 or findings:
        status = "Perlu Revisi"
    else:
        status = "Siap Terbit"
    return score, status


def _counts(findings: list[dict]) -> dict:
    counts = {"ambigu": 0, "regulasi": 0, "gaya": 0, "reputasi": 0}
    for item in findings:
        counts[item["kategori"]] = counts.get(item["kategori"], 0) + 1
    return counts


def _empty(message: str) -> dict:
    return {
        "disclaimer": DISCLAIMER,
        "original": "",
        "revised": "",
        "findings": [],
        "score": 0,
        "status": "Perlu Revisi",
        "counts": _counts([]),
        "error": message,
        "method": "aturan",
    }


def _document_xml(lines: list[str]) -> str:
    body = []
    for line in lines:
        safe = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        body.append(f"<w:p><w:r><w:t xml:space=\"preserve\">{safe}</w:t></w:r></w:p>")
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{''.join(body)}</w:body></w:document>"
    )


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
