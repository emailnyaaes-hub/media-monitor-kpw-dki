"""Analisis kutipan UU/pasal, implikasi pelanggaran hukum substansi, dan implikasi bahasa.

Katalog pasal bersifat indikatif untuk alat bantu review; tetap wajib verifikasi Unit Hukum.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

UU_PASAL_MAX = {
    (4, 2023): 165,
    (8, 1999): 61,
    (11, 2008): 54,
    (13, 2016): 463,
    (14, 2008): 77,
    (19, 2016): 55,
    (20, 2016): 20,
    (23, 1999): 74,
    (27, 2022): 76,
    (28, 2014): 198,
    (31, 2000): 122,
}

UU_NAMES = {
    (4, 2023): "UU No. 4 Tahun 2023 tentang P2SK",
    (8, 1999): "UU No. 8 Tahun 1999 tentang Perlindungan Konsumen",
    (11, 2008): "UU No. 11 Tahun 2008 tentang ITE",
    (19, 2016): "UU No. 19 Tahun 2016 tentang ITE",
    (23, 1999): "UU No. 23 Tahun 1999 tentang Bank Indonesia",
    (27, 2022): "UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi",
    (14, 2008): "UU No. 14 Tahun 2008 tentang KIP",
    (28, 2014): "UU No. 28 Tahun 2014 tentang Hak Cipta",
    (31, 2000): "UU No. 31 Tahun 2000 tentang Desain Tata Uang Rupiah",
}


@dataclass(frozen=True)
class PasalProfile:
    ringkas: str
    cocok: re.Pattern[str]
    tidak_cocok: re.Pattern[str] | None = None


PASAL_PROFILES: dict[tuple[int, int, int], PasalProfile] = {
    (8, 1999, 4): PasalProfile(
        "hak konsumen atas informasi yang benar",
        re.compile(r"informasi|konsumen|hak|benar|jelas|identitas|komplain|komunikasi", re.I),
        re.compile(r"fitnah|penghinaan|mengakses ilegal|siber|pencucian", re.I),
    ),
    (8, 1999, 18): PasalProfile(
        "larangan iklan yang menyesatkan",
        re.compile(r"iklan|promosi|menyesatkan|menjanjikan|klaim|konsumen|pemasaran", re.I),
        re.compile(r"data pribadi|surat elektronik|akses tanpa izin|BI-Rate", re.I),
    ),
    (8, 1999, 9): PasalProfile(
        "larangan pelaku usaha tertentu",
        re.compile(r"pelaku usaha|larangan|konsumen|barang|jasa", re.I),
        re.compile(r"kebijakan moneter|suku bunga|bank sentral", re.I),
    ),
    (8, 1999, 12): PasalProfile(
        "penyelesaian sengketa konsumen",
        re.compile(r"sengketa|konsumen|mediasi|penyelesaian|keluhan", re.I),
        re.compile(r"menjamin untung|jaminan profit|suku bunga|BI-Rate", re.I),
    ),
    (19, 2016, 27): PasalProfile(
        "larangan muatan dalam sistem elektronik (TERMASUK fitnah/berita bohong)",
        re.compile(
            r"muatan|siarkan|transaksikan|fitnah|hoaks|bohong|menghina|mencemarkan|"
            r"hasutan|pornografi|perjudian|elektronik|ITE",
            re.I,
        ),
        re.compile(r"konsumen|jaminan|suku bunga|kebijakan moneter|barang dagang", re.I),
    ),
    (19, 2016, 28): PasalProfile(
        "kegiatan terlarang terkait sistem elektronik (akses/data)",
        re.compile(r"akses|sistem|data|elektronik|peretas|meretas", re.I),
        re.compile(r"iklan menyesatkan|konsumen|hak konsumen", re.I),
    ),
    (11, 2008, 27): PasalProfile(
        "larangan muatan ITE (UU asal sebelum diubah UU 19/2016)",
        re.compile(r"muatan|fitnah|hoaks|menghina|elektronik|siarkan", re.I),
        re.compile(r"konsumen|jaminan investasi", re.I),
    ),
    (27, 2022, 4): PasalProfile(
        "definisi data pribadi",
        re.compile(r"data pribadi|pribadi|identitas|NIK|alamat|biometrik", re.I),
        re.compile(r"suku bunga|kebijakan moneter|iklan", re.I),
    ),
    (27, 2022, 14): PasalProfile(
        "kewajiban perlindungan data pribadi",
        re.compile(r"data pribadi|melindungi|pengumpulan|persetujuan|pihak terkait", re.I),
        re.compile(r"fitnah|hoaks|konsumen", re.I),
    ),
    (23, 1999, 7): PasalProfile(
        "mandat Bank Indonesia",
        re.compile(r"Bank Indonesia|stabilitas|nilai tukar|sistem pembayaran|rupiah|moneter", re.I),
        re.compile(r"konsumen|hak cipta|data pribadi", re.I),
    ),
}


CITE_PASAL_UU = re.compile(
    r"Pasal\s+(?P<pasal>\d+)[A-Za-z]?(?:\s+ayat\s*\((?P<ayat>\d+)\))?"
    r"(?P<mid>.{0,160})?"
    r"(?:UU\s*(?:No\.?|Nomor)?\s*(?P<num>\d+)\s*(?:Tahun|Th\.?)\s*(?P<tahun>\d{4}))"
    r"|"
    r"(?:UU\s*(?:No\.?|Nomor)?\s*(?P<num2>\d+)\s*(?:Tahun|Th\.?)\s*(?P<tahun2>\d{4}))"
    r"(?P<mid2>.{0,160})?"
    r"Pasal\s+(?P<pasal2>\d+)[A-Za-z]?(?:\s+ayat\s*\((?P<ayat2>\d+)\))?",
    re.I | re.S,
)

PASAL_ONLY = re.compile(r"\bPasal\s+(\d+)[A-Za-z]?(?:\s+ayat\s*\(\d+\))?", re.I)

IMPLIKASI_SUBSTANSI = [
    (
        re.compile(
            r"\b(terbukti|sudah jelas|tanpa keraguan)\b.*\b(bersalah|melakukan|bersifat)\b",
            re.I | re.S,
        ),
        "Tinggi",
        "Substansi draf memuat pernyataan bersalah atau kesalahan seolah sudah terbukti tanpa proses hukum.",
        "UU No. 19 Tahun 2016 tentang ITE (muatan hukum pidana/elektronik). Perlu verifikasi tim Hukum.",
        "Gunakan bahasa fakta yang sudah diumumkan resmi (putusan/surat resmi), bukan label bersalah.",
        "Menyatakan kesalahan terbukti tanpa dasar resmi berpotensi melanggar norma penghinaan/ITE.",
    ),
    (
        re.compile(
            r"\b\d{16}\b|\bNIK\b.*\b\d",
            re.I,
        ),
        "Tinggi",
        "Draf dapat menyebar data identitas yang dilindungi.",
        "UU No. 27 Tahun 2022 tentang PDP. Perlu verifikasi tim Hukum.",
        "Hapus identitas; gunakan ilustrasi tanpa data orang sungguhan.",
        "Penyebaran data pribadi tanpa dasar dapat menimbulkan pelanggaran PDP.",
    ),
    (
        re.compile(r"\b(menghasut|provokasi|mengadu domba)\b", re.I),
        "Tinggi",
        "Bahasa dapat dibaca sebagai hasutan atau provokasi.",
        "KUHP dan norma pidana. Perlu verifikasi tim Hukum.",
        "Ganti dengan komunikasi edukatif tanpa ajakan konfrontasi.",
        "Hasutan memiliki implikasi pidana dan reputasi serius.",
    ),
    (
        re.compile(
            r"\b(penipuan|menipu|membohongi|memperdaya)\b(?!\s+yang\s+dilakukan\s+oknum\s+luar)",
            re.I,
        ),
        "Sedang",
        "Draf menyatakan atau mengimplikasikan penipuan tanpa konteks kejadian resmi.",
        "KUHP (pidana penipuan) dan UU No. 8 Tahun 1999. Perlu verifikasi tim Hukum.",
        "Sebut fakta resmi (rilis/SP/KPU) bila melaporkan modus; hindari label penipuan tanpa dasar.",
        "Penuduhan penipuan tanpa bukti dapat menimbulkan tuntutan hukum.",
    ),
    (
        re.compile(r"\b(jaminan\s+keuntungan|pasti\s+untung|return\s+past[i]?)\b", re.I),
        "Tinggi",
        "Substansi menjanjikan imbal hasil finansial.",
        "UU No. 8 Tahun 1999 tentang Perlindungan Konsumen. Perlu verifikasi tim Hukum.",
        "Hapus janji imbal hasil; edukasi risiko produk keuangan secara umum.",
        "Janji keuntungan finansial dari komunikasi BI berisiko perlindungan konsumen.",
    ),
]

IMPLIKASI_BAHASA = [
    (
        re.compile(r"\b(bersalah|terbukti bersalah|melakukan kejahatan)\b.*\b(namanya|bernama|yaitu|ialah)\b", re.I | re.S),
        "Tinggi",
        "Bahasa menuding orang teridentifikasi seolah sudah dihukum.",
        "UU No. 19 Tahun 2016 tentang ITE. Perlu verifikasi tim Hukum.",
        "Ubah menjadi fakta putusan resmi atau hapus penamaan.",
        "Pernyataan bersalah terhadap orang yang bisa diidentifikasi berimplikasi pidana.",
    ),
    (
        re.compile(r"\b(fitnah|memfitnah|mencemarkan nama baik|mencemarkan integritas)\b", re.I),
        "Tinggi",
        "Bahasa fitnah atau pencemaran nama baik.",
        "UU No. 19 Tahun 2016 tentang ITE. Perlu verifikasi tim Hukum.",
        "Ganti dengan ujaran faktual dan bermediasi sumber resmi; hindari label hukum pidana.",
        "Istilah fitnah memiliki implikasi pidana langsung.",
    ),
    (
        re.compile(r"\b(melanggar\s+hukum|secara\s+hukum\s+melanggar|terbukti\s+melanggar)\b", re.I),
        "Sedang",
        "Bahasa menyatakan pelanggaran hukum tanpa merujuk putusan atau rilis resmi.",
        "Norma pidana dan tata cara penegakan hukum. Perlu verifikasi tim Hukum.",
        "Ganti dengan «diduga» hanya bila rilis penegak hukum; atau «dikhawatirkan melanggar ketentuan …» setelah verifikasi Hukum.",
        "Menyatakan seseorang/lembaga melanggar hukum tanpa proses adalah risiko hukum.",
    ),
    (
        re.compile(r"\b(wajib\s+dipenjara|harus\s+ditahan|past[i]?\s+divonis)\b", re.I),
        "Tinggi",
        "Bahasa mengantisipasi atau memvonis hukuman.",
        "KUHP / hukum acara pidana. Perlu verifikasi tim Hukum.",
        "Hapus spekulasi hukuman; kehumasan tidak memvonis.",
        "Bahasa vonis/hukuman mengganggu hak proses hukum.",
    ),
    (
        re.compile(r"\bmenurut\s+(UU|undang-undang)\b.*\b(wajib|dilarang keras|dihukum)\b", re.I | re.S),
        "Sedang",
        "Bahasa menginterpretasi UU secara tegas pada publik tanpa konteks lengkap.",
        "UU terkait sesuai rujukan. Perlu verifikasi tim Hukum.",
        "Gunakan ringkasan bermatra rilis Hukum, bukan interpretasi mandiri.",
        "Interpretasi hukum pada draf publik dapat menimbulkan salah tafsir.",
    ),
    (
        re.compile(r"\b(sepakat|sepasal)\s+Pasal\s+\d+", re.I),
        "Tinggi",
        "Bahasa menyetujui/membenarkan nomor pasal tanpa verifikasi (termasuk salah ketik «sepasal»).",
        "Rujukan peraturan. Perlu verifikasi tim Hukum.",
        "Hapus rujukan pasal dari draf publik; serahkan ke Unit Hukum.",
        "Membenarkan pasal pada naskah publik berisiko kutipan keliru.",
    ),
]


def analyze(text: str, make_finding: Callable[..., dict]) -> list[dict]:
    findings: list[dict] = []
    findings.extend(_citation_checks(text, make_finding))
    findings.extend(_pattern_checks(text, IMPLIKASI_SUBSTANSI, make_finding, "Substansi"))
    findings.extend(_pattern_checks(text, IMPLIKASI_BAHASA, make_finding, "Bahasa"))
    return findings


def _sentence_bounds(text: str, index: int) -> tuple[int, int]:
    start = max(
        text.rfind(".", 0, index),
        text.rfind("!", 0, index),
        text.rfind("?", 0, index),
        text.rfind("\n", 0, index),
    )
    start = 0 if start < 0 else start + 1
    ends = [text.find(m, index) for m in ".!?\n"]
    ends = [e for e in ends if e >= 0]
    end = (min(ends) + 1) if ends else len(text)
    return start, end


def _parse_pasal_num(raw: str) -> int:
    return int(re.match(r"\d+", raw).group(0))


def _citation_checks(text: str, make_finding: Callable[..., dict]) -> list[dict]:
    found: list[dict] = []
    for match in CITE_PASAL_UU.finditer(text):
        pasal_raw = match.group("pasal") or match.group("pasal2")
        uu_num = match.group("num") or match.group("num2")
        uu_year = match.group("tahun") or match.group("tahun2")
        if not (pasal_raw and uu_num and uu_year):
            continue
        pasal = _parse_pasal_num(pasal_raw)
        num, year = int(uu_num), int(uu_year)
        span_start, span_end = match.start(), match.end()
        hapus = match.group(0).strip()
        s_start, s_end = _sentence_bounds(text, span_start)
        sentence = text[s_start:s_end].strip()
        key = (num, year)
        uu_label = UU_NAMES.get(key, f"UU No. {num} Tahun {year}")

        pasal_max = UU_PASAL_MAX.get(key)
        if pasal_max and pasal > pasal_max:
            saran = f"[Hapus rujukan] — Pasal {pasal} tidak teridentifikasi pada {uu_label} (katalog internal hingga Pasal {pasal_max})."
            found.append(
                make_finding(
                    s_start,
                    s_end,
                    sentence,
                    "implikasi_hukum",
                    "Tinggi",
                    f"Pasal {pasal} dirujuk pada {uu_label}, tetapi nomor pasal melampaui katalog internal (maks. {pasal_max}).",
                    f"{uu_label}. Perlu verifikasi tim Hukum.",
                    saran,
                    "Kutipan pasal yang tidak ada menggugurkan dalil hukum dan memperburuk risiko reputasi.",
                    span_start=span_start,
                    span_end=span_end,
                    hapus=hapus,
                    tambah="[rujukan hukum diverifikasi Unit Hukum]",
                )
            )
            continue

        profile = PASAL_PROFILES.get((num, year, pasal))
        if not profile and pasal_max and 1 <= pasal <= pasal_max:
            found.append(
                make_finding(
                    s_start,
                    s_end,
                    sentence,
                    "implikasi_hukum",
                    "Sedang",
                    f"Pasal {pasal} pada {uu_label} perlu dicek substansi dan kebenaran nomornya.",
                    f"{uu_label}. Perlu verifikasi tim Hukum.",
                    "Serahkan kutipan kepada Unit Hukum; publikasi hanya memuat ringkasan bermatra.",
                    "Pasal tanpa verifikasi berisiko salah kutip.",
                    span_start=span_start,
                    span_end=span_end,
                    hapus=hapus,
                    tambah=None,
                )
            )
            continue

        if profile:
            if profile.tidak_cocok and profile.tidak_cocok.search(sentence):
                found.append(
                    make_finding(
                        s_start,
                        s_end,
                        sentence,
                        "implikasi_hukum",
                        "Tinggi",
                        f"Substansi kalimat tidak selaras dengan Pasal {pasal} ({profile.ringkas}) pada {uu_label}.",
                        f"{uu_label}. Perlu verifikasi tim Hukum.",
                        "Ubah substansi atau ganti rujukan setelah konfirmasi Hukum; jangan memaksakan pasal yang tidak relevan.",
                        "Rujukan pasal yang tidak relevan dapat dianggap misleading dan membahayakan posisi hukum BI.",
                        span_start=span_start,
                        span_end=span_end,
                        hapus=hapus,
                        tambah="[substansi diselaraskan dengan rujukan Unit Hukum]",
                    )
                )
            elif not profile.cocok.search(sentence):
                found.append(
                    make_finding(
                        s_start,
                        s_end,
                        sentence,
                        "implikasi_hukum",
                        "Sedang",
                        f"Konteks kalimat tidak jelas mencerminkan lingkup Pasal {pasal} ({profile.ringkas}).",
                        f"{uu_label}. Perlu verifikasi tim Hukum.",
                        f"Perjelas isu: kaitkan fakta dengan {profile.ringkas}, atau hapus nomor pasal dari draf publik.",
                        "Rujukan pasal tanpa kaitan substansi melemahkan kredibilitas hukum naskah.",
                        span_start=span_start,
                        span_end=span_end,
                        hapus=hapus,
                        tambah=None,
                    )
                )

    for match in PASAL_ONLY.finditer(text):
        pasal = _parse_pasal_num(match.group(1))
        window_start = max(0, match.start() - 200)
        window = text[window_start : match.end() + 200]
        if not re.search(r"\bUU\s*(?:No\.?|Nomor)?\s*\d+", window, re.I):
            continue
        if CITE_PASAL_UU.search(window):
            continue
        s_start, s_end = _sentence_bounds(text, match.start())
        sentence = text[s_start:s_end].strip()
        hapus = match.group(0)
        found.append(
            make_finding(
                s_start,
                s_end,
                sentence,
                "implikasi_hukum",
                "Sedang",
                f"Pasal {pasal} disebut tanpa pasangan UU yang terbaca jelas dalam satu kutipan.",
                "Rujukan peraturan. Perlu verifikasi tim Hukum.",
                "Cantumkan UU lengkap pada catatan internal; draf publik tidak perlu nomor pasal.",
                "Kutipan pasal yang terpisah dari UU rentan salah.",
                span_start=match.start(),
                span_end=match.end(),
                hapus=hapus,
                tambah="",
            )
        )
    return found


def _pattern_checks(
    text: str,
    rules: list[tuple],
    make_finding: Callable[..., dict],
    label: str,
) -> list[dict]:
    found: list[dict] = []
    for pattern, risk, problem, legal, saran, reason in rules:
        for match in pattern.finditer(text):
            span_start, span_end = match.start(), match.end()
            s_start, s_end = _sentence_bounds(text, span_start)
            sentence = text[s_start:s_end].strip()
            hapus = text[span_start:span_end]
            tambah = None
            if risk == "Tinggi" and len(hapus) < 80:
                tambah = "[kalimat ditinjau ulang Unit Hukum]"
            found.append(
                make_finding(
                    s_start,
                    s_end,
                    sentence,
                    "implikasi_hukum",
                    risk,
                    f"Implikasi hukum ({label}): {problem}",
                    legal,
                    saran,
                    reason,
                    span_start=span_start,
                    span_end=span_end,
                    hapus=hapus if len(hapus) < 120 else sentence,
                    tambah=tambah,
                )
            )
    return found
