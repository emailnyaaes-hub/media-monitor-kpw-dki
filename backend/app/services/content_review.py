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

from app.nlp.bi_style import BI_REVIEW_SUFFIX, BI_VOICE_GUIDE
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
    (
        re.compile(r"\b(korup|korupsi|penipuan|pencucian uang)\b.*\b(namanya|bernama|ialah)\b", re.I),
        "regulasi",
        "Tinggi",
        "Draf dapat menuduh orang tertentu tanpa putusan atau sumber resmi.",
        "UU No. 19 Tahun 2016 tentang Perubahan atas UU No. 11 Tahun 2008 tentang Informasi dan Transaksi Elektronik. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Gunakan fakta yang sudah diumumkan resmi dan hindari penuduhan personal.",
        "Penghinaan atau fitnah atas orang yang dapat diidentifikasi berisiko hukum.",
    ),
    (
        re.compile(r"\bUU\s*(No\.?\s*)?\d+\s*Tahun\s*\d{4}\b", re.I),
        "regulasi",
        "Sedang",
        "Undang-undang disebut pada draf publik; pastikan kutipan dan konteksnya sudah diverifikasi Hukum.",
        "Rujukan peraturan perundang-undangan (UU). Pasal tidak disebut. Perlu verifikasi tim Hukum.",
        "Pastikan nama UU tepat dan tidak disertai interpretasi hukum yang belum disetujui Unit Hukum.",
        "Menyebut UU tanpa peninjauan dapat menimbulkan salah tafsir ketentuan.",
    ),
]

KATA_BAKU_RULES = [
    (re.compile(r"\baktifitas\b", re.I), "aktivitas", "KBBI merekomendasikan bentuk 'aktivitas'."),
    (re.compile(r"\bpraktek\b", re.I), "praktik", "Untuk pengertian kegiatan latihan atau usaha, KBBI memakai 'praktik'."),
    (re.compile(r"\bresiko\b", re.I), "risiko", "Ejaan baku menurut KBBI adalah 'risiko'."),
    (re.compile(r"\bfrekwensi\b", re.I), "frekuensi", "Ejaan baku menurut KBBI adalah 'frekuensi'."),
    (re.compile(r"\banalisa\b", re.I), "analisis", "KBBI memakai 'analisis' untuk bentuk kata benda."),
    (re.compile(r"\bapotik\b", re.I), "apotek", "KBBI memakai 'apotek'."),
    (re.compile(r"\bemail\b", re.I), "surel", "Bahasa Indonesia baku untuk surel elektronik adalah 'surel'."),
    (re.compile(r"\binfo\b", re.I), "informasi", "'Informasi' lebih sesuai ragam resmi."),
    (re.compile(r"\bupdate\b", re.I), "pembaruan", "Dalam ragam resmi, gunakan 'pembaruan' atau 'mutakhirkan' sesuai konteks."),
    (re.compile(r"\baccount\b", re.I), "akun", "Serapan resmi KBBI: 'akun'."),
    (re.compile(r"\bdownload\b", re.I), "unduh", "KBBI merekomendasikan 'unduh'."),
    (re.compile(r"\bupload\b", re.I), "unggah", "KBBI merekomendasikan 'unggah'."),
    (re.compile(r"\bsharing\b", re.I), "berbagi", "Gunakan padanan Indonesia 'berbagi' atau 'membagikan'."),
]

KEJELASAN_PATTERNS = [
    (
        re.compile(r"\b(dll\.?|dan sebagainya|dan lain-lain)\b", re.I),
        "Frasa penutup yang tidak spesifik; pembaca tidak tahu apa yang ikut dimaksud.",
        "Sebutkan contoh atau jenis yang dimaksud, atau hilangkan jika tidak perlu.",
        "Daftar terbuka seperti 'dan lain-lain' menimbulkan ambiguitas.",
    ),
    (
        re.compile(r"\b(segera|secepatnya|dalam waktu dekat)\b", re.I),
        "Batas waktu tidak tertulis; dapat ditafsirkan berbeda oleh pembaca.",
        "Cantumkan tanggal, periode, atau syarat resmi yang sudah disetujui.",
        "Tanpa patokan waktu, janji operasional mudah disalahpahami.",
    ),
    (
        re.compile(r"\bbeberapa\s+(pihak|oknum|orang)\b", re.I),
        "Subjek tidak jelas sehingga pernyataan sulit dipertanggungjawabkan.",
        "Sebutkan lembaga, peran, atau gunakan kalimat pasif yang tetap faktual.",
        "Frasa umum menutupi siapa yang dimaksud.",
    ),
    (
        re.compile(r"\b(mungkin|barangkali|kira-kira)\b.*\b(akan|bisa)\b", re.I),
        "Gabungan kata ragu dan prediksi dapat dibaca sebagai komitmen BI.",
        "Pisahkan fakta yang sudah pasti dari perkiraan, atau hapus prediksi.",
        "Hedging dan prediksi bersama membingungkan tingkat kepastian.",
    ),
]


def review(text: str, kind: str = "siaran", platform: str = "") -> dict:
    original = (text or "").strip()
    if len(original) < 20:
        return _empty("Teks terlalu pendek untuk ditinjau.")
    findings = []
    for chunk_start, chunk in _chunks(original):
        findings.extend(_rules(chunk, chunk_start))
        findings.extend(_kata_baku(chunk, chunk_start))
        findings.extend(_kejelasan(chunk, chunk_start))
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
        "track": track_changes_view(original, findings),
        "method": "aturan" if not os.environ.get("LLM_API_KEY", "").strip() else "aturan+model",
    }


def apply_all(original: str, findings: list[dict]) -> str:
    accepted = [item for item in findings if item.get("accepted", True)]
    accepted.sort(key=lambda item: item.get("span_start", item["start"]), reverse=True)
    text = original
    for item in accepted:
        start = item.get("span_start", item["start"])
        end = item.get("span_end", item["end"])
        tambah = item.get("tambah")
        if tambah is None:
            if start == item["start"] and end == item["end"]:
                tambah = item.get("saran") or ""
            else:
                continue
        if tambah == "" and not item.get("hapus"):
            continue
        if 0 <= start < end <= len(text):
            text = text[:start] + tambah + text[end:]
    return text


def track_changes_view(original: str, findings: list[dict]) -> list[dict]:
    """Potongan teks untuk tampilan track changes: teks biasa, coretan, atau sisipan."""
    regions = []
    for item in findings:
        if not item.get("accepted", True):
            continue
        a = item.get("span_start", item["start"])
        b = item.get("span_end", item["end"])
        hapus = item.get("hapus")
        if hapus is None and 0 <= a < b <= len(original):
            hapus = original[a:b]
        tambah = item.get("tambah")
        if tambah is None:
            tambah = item.get("saran") or ""
        regions.append({
            "start": a,
            "end": b,
            "hapus": hapus,
            "tambah": tambah,
            "kategori": item.get("kategori"),
            "alasan": item.get("alasan", ""),
            "dasar_hukum": item.get("dasar_hukum", ""),
        })
    regions.sort(key=lambda r: r["start"])
    pieces = []
    cursor = 0
    for region in regions:
        if region["start"] < cursor:
            continue
        if region["start"] > cursor:
            pieces.append({"tipe": "teks", "isi": original[cursor:region["start"]]})
        if region.get("hapus"):
            pieces.append({"tipe": "hapus", "isi": region["hapus"], "kategori": region.get("kategori"), "alasan": region.get("alasan")})
        if region.get("tambah"):
            pieces.append({"tipe": "tambah", "isi": region["tambah"], "kategori": region.get("kategori"), "alasan": region.get("alasan")})
        cursor = max(cursor, region["end"])
    if cursor < len(original):
        pieces.append({"tipe": "teks", "isi": original[cursor:]})
    return pieces


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
        lines.append(f"- [{item.get('kategori')}] [{item.get('risiko')}] {item.get('masalah')}")
        if item.get("hapus") or item.get("tambah"):
            lines.append(f"  Track: «{item.get('hapus', '')}» → «{item.get('tambah', item.get('saran', ''))}»")
        lines.append(f"  Saran: {item.get('saran')}")
        lines.append(f"  Alasan: {item.get('alasan')}")
        lines.append(f"  Dasar: {item.get('dasar_hukum')}")
    lines.extend(["", "Versi asli", original])
    document = _document_xml(lines, findings)
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
            span_start = offset + match.start()
            span_end = offset + match.end()
            sentence_start = offset + _sentence_start(chunk, match.start())
            sentence_end = offset + _sentence_end(chunk, match.end())
            sentence = chunk[sentence_start - offset:sentence_end - offset].strip()
            hapus = chunk[match.start():match.end()]
            tambah = _regulasi_tambah(hapus, suggestion)
            found.append(_finding(
                sentence_start, sentence_end, sentence, category, risk, problem, legal, suggestion, reason,
                span_start=span_start, span_end=span_end, hapus=hapus, tambah=tambah,
            ))
    return found


def _regulasi_tambah(hapus: str, suggestion: str) -> str | None:
    lower = suggestion.lower()
    if "hapus" in lower and "nomor" in lower:
        return ""
    if re.fullmatch(r"[\w.+-]+@[\w.-]+\.\w+", hapus or ""):
        return "saluran resmi Bank Indonesia"
    if re.fullmatch(r"\b\d{16}\b", hapus or ""):
        return ""
    return None


def _kata_baku(chunk: str, offset: int) -> list[dict]:
    found = []
    for pattern, replacement, reason in KATA_BAKU_RULES:
        for match in pattern.finditer(chunk):
            span_start = offset + match.start()
            span_end = offset + match.end()
            hapus = chunk[match.start():match.end()]
            sentence_start = offset + _sentence_start(chunk, match.start())
            sentence_end = offset + _sentence_end(chunk, match.end())
            sentence = chunk[sentence_start - offset:sentence_end - offset].strip()
            new_sentence = sentence[: match.start() - (sentence_start - offset)] + replacement + sentence[match.end() - (sentence_start - offset):]
            found.append(_finding(
                sentence_start, sentence_end, sentence, "kata_baku", "Rendah",
                f"Kata «{hapus}» bukan bentuk baku dalam ragam resmi.",
                "Pedoman Umum Ejaan Bahasa Indonesia / KBBI. Bukan pasal undang-undangan.",
                new_sentence.strip(),
                reason,
                span_start=span_start, span_end=span_end, hapus=hapus, tambah=replacement,
            ))
    return found


def _kejelasan(chunk: str, offset: int) -> list[dict]:
    found = []
    for pattern, problem, suggestion, reason in KEJELASAN_PATTERNS:
        for match in pattern.finditer(chunk):
            span_start = offset + match.start()
            span_end = offset + match.end()
            hapus = chunk[match.start():match.end()]
            sentence_start = offset + _sentence_start(chunk, match.start())
            sentence_end = offset + _sentence_end(chunk, match.end())
            sentence = chunk[sentence_start - offset:sentence_end - offset].strip()
            found.append(_finding(
                sentence_start, sentence_end, sentence, "kejelasan", "Sedang",
                problem,
                "Pedoman komunikasi yang jelas. Bukan pasal undang-undangan. Perlu verifikasi tim Hukum bila menyangkut substansi.",
                suggestion,
                reason,
                span_start=span_start, span_end=span_end, hapus=hapus, tambah=None,
            ))
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
            shorter = _shorten(sentence)
            found.append(_finding(
                start, end, sentence, "kejelasan", "Sedang",
                "Kalimat lebih dari 45 kata dan sulit diikuti dalam sekali baca.",
                "Pedoman komunikasi yang jelas. Bukan pasal undang-undang. Perlu verifikasi tim Hukum bila menyangkut substansi.",
                shorter,
                "Kalimat yang lebih pendek mengurangi tafsir ganda.",
                hapus=sentence, tambah=shorter,
            ))
        if re.search(r"\d", sentence) and not re.search(r"\b(20\d\d|periode|per |hingga|sampai|tahun|bulan)\b", sentence, re.I):
            patched = sentence.rstrip(".!?") + " (sebutkan periode dan sumber data)."
            found.append(_finding(
                start, end, sentence, "kejelasan", "Sedang",
                "Ada angka tanpa periode atau sumber yang tertulis pada kalimat yang sama.",
                "UU No. 8 Tahun 1999 tentang Perlindungan Konsumen. Pasal tidak disebut. Perlu verifikasi tim Hukum.",
                patched,
                "Angka tanpa periode mudah dibaca di luar konteks.",
                hapus=sentence, tambah=patched,
            ))
        if re.search(r"\b(gue|lo|gw|wkwk|anjir)\b", sentence, re.I):
            rewritten = re.sub(r"\b(gue|lo|gw)\b", "Anda", sentence, flags=re.I)
            rewritten = re.sub(r"\b(wkwk|anjir)\b", "", rewritten, flags=re.I)
            rewritten = re.sub(r"\s+", " ", rewritten).strip()
            found.append(_finding(
                start, end, sentence, "kata_baku", "Rendah",
                "Ada kata tidak baku untuk kanal resmi.",
                "Pedoman bahasa Indonesia. Bukan pasal undang-undang.",
                rewritten,
                "Kanal Bank Indonesia memakai ragam formal.",
                hapus=sentence, tambah=rewritten,
            ))
        if kind == "caption" and platform in {"X", "Twitter"} and len(sentence) > 240:
            trimmed = sentence[:220].rstrip() + "…"
            found.append(_finding(
                start, end, sentence, "kata_baku", "Rendah",
                "Caption untuk X lebih panjang dari 240 karakter.",
                "Batasan praktis platform, bukan peraturan perundang-undangan.",
                trimmed,
                "Caption yang terpotong otomatis kehilangan ujung kalimat.",
                hapus=sentence, tambah=trimmed,
            ))
    return found


def _llm(original: str, existing: list[dict]) -> list[dict]:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return []
    system = (
        f"{BI_VOICE_GUIDE}\n\n{BI_REVIEW_SUFFIX}\n\n"
        "Anda reviewer komunikasi Bank Indonesia. Balas JSON {\"findings\": [...]} . "
        "Periksa: (1) regulasi perundang-undangan—acu UU bila relevan tanpa nomor pasal; "
        "(2) kata baku Bahasa Indonesia; (3) kejelasan dan ketepatan kata. "
        "Prioritaskan temuan KRITIS yang menghalangi terbit. "
        "Setiap temuan: kalimat, kategori (regulasi|kata_baku|kejelasan|reputasi), risiko, masalah, dasar_hukum, "
        "saran (teks pengganti ragam siaran pers BI), alasan (dampak hukum/reputasi/persepsi), "
        "opsional hapus/tambah untuk track changes. "
        "Jangan menulis nomor pasal. Jika ragu: nama UU + 'Perlu verifikasi tim Hukum'. "
        "Jangan menambah fakta di luar draf."
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
        hapus = item.get("hapus")
        tambah = item.get("tambah")
        span_start = start
        span_end = end
        if hapus and isinstance(hapus, str) and hapus in sentence:
            local = sentence.find(hapus)
            span_start = start + local
            span_end = span_start + len(hapus)
        extra.append(_finding(
            start,
            end,
            sentence,
            str(item.get("kategori") or "kejelasan"),
            str(item.get("risiko") or "Sedang"),
            _no_pasal(str(item.get("masalah") or "")),
            legal,
            _no_pasal(str(item.get("saran") or sentence)),
            _no_pasal(str(item.get("alasan") or "")),
            span_start=span_start,
            span_end=span_end,
            hapus=str(hapus) if hapus else None,
            tambah=str(tambah) if tambah is not None else None,
        ))
    return extra


def _normalize_category(category: str) -> str:
    raw = (category or "").strip().lower()
    if raw in {"regulasi", "reputasi"}:
        return raw
    if raw in {"kata_baku", "gaya", "katabaku"}:
        return "kata_baku"
    if raw in {"kejelasan", "ambigu", "ketepatan"}:
        return "kejelasan"
    return "kejelasan"


def _finding(
    start,
    end,
    sentence,
    category,
    risk,
    problem,
    legal,
    suggestion,
    reason,
    *,
    span_start: int | None = None,
    span_end: int | None = None,
    hapus: str | None = None,
    tambah: str | None = None,
) -> dict:
    norm = _normalize_category(category)
    ss = span_start if span_start is not None else start
    se = span_end if span_end is not None else end
    out = {
        "start": start,
        "end": end,
        "span_start": ss,
        "span_end": se,
        "kalimat": sentence,
        "kategori": norm,
        "risiko": risk if risk in {"Tinggi", "Sedang", "Rendah"} else "Sedang",
        "masalah": problem,
        "dasar_hukum": _no_pasal(legal),
        "saran": suggestion,
        "alasan": reason,
        "accepted": True,
    }
    if hapus is not None:
        out["hapus"] = hapus
    if tambah is not None:
        out["tambah"] = tambah
    return out


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
    counts = {"regulasi": 0, "kata_baku": 0, "kejelasan": 0, "reputasi": 0}
    for item in findings:
        cat = _normalize_category(item.get("kategori", ""))
        counts[cat] = counts.get(cat, 0) + 1
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


def _document_xml(lines: list[str], findings: list[dict] | None = None) -> str:
    body = []
    for line in lines:
        safe = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        body.append(f"<w:p><w:r><w:t xml:space=\"preserve\">{safe}</w:t></w:r></w:p>")
    if findings:
        body.append("<w:p><w:r><w:t xml:space=\"preserve\">Track changes (diterima)</w:t></w:r></w:p>")
        for item in findings:
            if not item.get("accepted", True):
                continue
            hapus = item.get("hapus") or ""
            tambah = item.get("tambah") if item.get("tambah") is not None else (item.get("saran") or "")
            if not hapus and not tambah:
                continue
            esc_h = _xml_text(hapus)
            esc_t = _xml_text(tambah)
            body.append(
                "<w:p>"
                f"<w:del><w:r><w:delText xml:space=\"preserve\">{esc_h}</w:delText></w:r></w:del>"
                f"<w:ins><w:r><w:t xml:space=\"preserve\">{esc_t}</w:t></w:r></w:ins>"
                "</w:p>"
            )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{''.join(body)}</w:body></w:document>"
    )


def _xml_text(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
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
