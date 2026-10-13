"""Klasifikasi Suara Publik dari judul dan cuplikan yang sudah tersimpan.

Aturan leksikon, bukan model yang mengarang isi. Koreksi analis menimpa
leksikon. Lokasi hanya dipakai bila sudah tertulis di data. Dugaan
penyebab selalu berlabel Hipotesis AI.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from app.constants import DISCLAIMER, JAKARTA_AREAS
from app.nlp import normalize
from app.services.serialize import loads

VOICES = ("keluhan", "apresiasi", "kebutuhan", "hoaks")
VOICE_LABEL = {
    "ramai": "Ramai",
    "keluhan": "Keluhan",
    "apresiasi": "Apresiasi",
    "kebutuhan": "Kebutuhan dan harapan",
    "hoaks": "Salah paham dan hoaks",
}

VOICE_TERMS = {
    "keluhan": (
        "keluhan", "komplain", "kecewa", "kesal", "sulit", "bingung", "ribet",
        "error", "gagal", "gangguan", "lambat", "antri", "mahal", "palsu",
        "tidak bisa", "tidak dapat", "bermasalah",
    ),
    "apresiasi": (
        "memudahkan", "mudah", "lancar", "terbantu", "puas", "apresiasi",
        "bermanfaat", "praktis", "membantu", "sukses",
    ),
    "kebutuhan": (
        "diharapkan", "harapan", "butuh", "perlu edukasi", "minta", "sosialisasi",
        "diperluas", "akses", "literasi", "dibutuhkan",
    ),
    "hoaks": (
        "hoaks", "hoax", "penipuan", "mengatasnamakan", "modus", "phishing",
        "lowongan palsu", "undian",
    ),
}

SEGMENTS = (
    ("UMKM dan pedagang", ("umkm", "pedagang", "merchant", "warung", "pasar")),
    ("Konsumen dan rumah tangga", ("konsumen", "rumah tangga", "belanja", "ibu rumah")),
    ("Anak muda dan mahasiswa", ("mahasiswa", "anak muda", "kampus", "gen z")),
    ("Pelaku fintech dan merchant", ("fintech", "gopay", "dana", "ovo", "qris merchant")),
    ("Pengemudi dan pekerja informal", ("ojol", "pengemudi", "driver", "pekerja informal")),
    ("Akademisi dan pengamat", ("ekonom", "pengamat", "akademisi", "peneliti")),
    ("Media", ()),
)
SEGMENT_IDS = [name for name, _ in SEGMENTS] + ["segmen tidak teridentifikasi"]

TOPIC_BY_CATEGORY = {
    "Ekonomi Jakarta": "Ekonomi Jakarta",
    "Inflasi": "Inflasi dan harga",
    "Rupiah/Kurs": "Rupiah/kurs",
    "Kebijakan Moneter": "Suku bunga",
    "Sistem Pembayaran": "Sistem pembayaran",
    "Pengedaran Uang": "Pengedaran uang",
    "Perbankan/Kredit": "Perbankan/kredit",
    "Reputasi/Kelembagaan": "Persepsi terhadap BI",
    "Kegiatan KPw DKI": "Persepsi terhadap BI",
    "Hoaks/Penipuan": "Persepsi terhadap BI",
    "Lainnya": "Persepsi terhadap BI",
}
TOPICS = (
    "Ekonomi Jakarta",
    "Inflasi dan harga",
    "Rupiah/kurs",
    "Suku bunga",
    "Sistem pembayaran",
    "Pengedaran uang",
    "UMKM",
    "Perbankan/kredit",
    "Persepsi terhadap BI",
)

# Setiap narasi: semua kelompok harus cocok, di dalam kelompok cukup satu kata.
NARRATIVES = (
    ("QRIS memudahkan", (("qris",), ("mudah", "memudahkan", "lancar", "praktis"))),
    ("Gangguan layanan pembayaran", (("qris", "bi-fast", "bifast", "transfer"), ("gagal", "error", "gangguan", "lambat"))),
    ("BI tidak peduli rakyat kecil", (("bank indonesia",), ("tidak peduli", "rakyat kecil", "masyarakat kecil"))),
    ("Uang palsu dan penukaran", (("uang palsu", "penukaran uang", "uang lusuh"),)),
    ("Hoaks mengatasnamakan BI", (("hoaks", "penipuan", "mengatasnamakan", "undian"), ("bank indonesia",))),
    ("Harga pangan naik", (("harga", "pangan", "cabai", "beras", "minyak goreng"), ("naik", "mahal", "melonjak"))),
    ("Suku bunga membebani", (("bunga", "bi-rate", "suku bunga"), ("tinggi", "mahal", "beban", "berat"))),
)

# Opsi tindakan yang masuk akal bagi kewenangan komunikasi dan koordinasi BI.
# Bukan saran mengubah kebijakan moneter.
SOLUTIONS = (
    {
        "id": "bayar",
        "voices": ("keluhan",),
        "terms": ("qris", "bi-fast", "bifast", "error", "gangguan", "gagal"),
        "keluhan": "Kesulitan atau gangguan pada pembayaran digital",
        "kebutuhan": "",
        "tindakan": "Minta unit Sistem Pembayaran mengecek apakah ada gangguan layanan, lalu siapkan edukasi langkah bila transaksi gagal. Jangan mengumumkan status layanan sebelum ada konfirmasi.",
        "jenis": "koordinasi dan edukasi",
        "unit": "Sistem Pembayaran",
        "luar": False,
    },
    {
        "id": "hoaks",
        "voices": ("hoaks",),
        "terms": ("hoaks", "penipuan", "mengatasnamakan", "undian", "phishing"),
        "keluhan": "Pola bahasa hoaks atau penipuan mengatasnamakan BI",
        "kebutuhan": "Klarifikasi yang bisa dicek ke sumber asli",
        "tindakan": "Siapkan klarifikasi hanya setelah isi unggahan dicek pada tautan sumber. Sertakan cara mengenali kanal resmi. Ini deteksi kata, bukan penetapan bahwa konten itu hoaks.",
        "jenis": "klarifikasi hoaks",
        "unit": "Kehumasan",
        "luar": False,
    },
    {
        "id": "edukasi",
        "voices": ("kebutuhan",),
        "terms": ("edukasi", "sosialisasi", "literasi"),
        "keluhan": "",
        "kebutuhan": "Permintaan edukasi atau literasi",
        "tindakan": "Susun materi edukasi dari pertanyaan yang benar-benar tertulis di konten. Jangan menambah janji program.",
        "jenis": "konten edukasi",
        "unit": "Kehumasan KPw DKI",
        "luar": False,
    },
    {
        "id": "harga",
        "voices": ("keluhan", "kebutuhan"),
        "terms": ("harga pangan", "cabai", "beras", "minyak goreng", "sembako"),
        "keluhan": "Keluhan harga pangan",
        "kebutuhan": "Harga yang lebih stabil",
        "tindakan": "Sampaikan persepsi publik ke forum TPID. Penetapan harga ada di luar kewenangan Bank Indonesia.",
        "jenis": "koordinasi pihak lain",
        "unit": "TPID dan pemerintah daerah",
        "luar": True,
    },
    {
        "id": "uang",
        "voices": ("keluhan", "kebutuhan"),
        "terms": ("uang palsu", "penukaran", "uang lusuh", "tidak layak edar"),
        "keluhan": "Kesulitan penukaran uang atau temuan uang palsu",
        "kebutuhan": "Cara menukar uang dan mengenali uang palsu",
        "tindakan": "Siapkan edukasi ciri uang dan jadwal layanan yang sudah ada. Jangan mengumumkan jadwal kas keliling yang tidak tercantum di sumber.",
        "jenis": "konten edukasi",
        "unit": "Pengedaran Uang",
        "luar": False,
    },
    {
        "id": "bunga",
        "voices": ("keluhan",),
        "terms": ("bunga kredit", "suku bunga", "bi-rate"),
        "keluhan": "Keberatan atas suku bunga atau bunga kredit",
        "kebutuhan": "",
        "tindakan": "Sampaikan persepsi publik ke unit Kebijakan Moneter. Jangan merumuskan saran mengubah BI-Rate. Bunga kredit bank individual perlu koordinasi pihak lain.",
        "jenis": "masukan persepsi",
        "unit": "Kebijakan Moneter",
        "luar": True,
    },
    {
        "id": "umkm",
        "voices": ("kebutuhan", "keluhan"),
        "terms": ("umkm", "pembiayaan", "modal usaha"),
        "keluhan": "",
        "kebutuhan": "Akses pembiayaan atau pendampingan UMKM",
        "tindakan": "Edukasi dapat disiapkan KPw. Penyaluran kredit perlu koordinasi perbankan, bukan diputus dari dashboard ini.",
        "jenis": "koordinasi pihak lain",
        "unit": "Kehumasan KPw DKI",
        "luar": True,
    },
    {
        "id": "apresiasi-bayar",
        "voices": ("apresiasi",),
        "terms": ("qris", "bi-fast", "kas keliling"),
        "keluhan": "",
        "kebutuhan": "",
        "tindakan": "Catat layanan yang dipuji agar materi edukasi memakai contoh yang sudah diberitakan. Bukan bahan kampanye.",
        "jenis": "respons komunikasi",
        "unit": "Kehumasan",
        "luar": False,
    },
)

SEASON_TERMS = ("ramadan", "lebaran", "idul fitri", "tahun ajaran", "akhir tahun", "natal")


def _hay(row) -> str:
    raw = (getattr(row, "title", "") or "") + " " + (getattr(row, "text", "") or "")
    return " " + normalize(raw) + " "


def _has_any(hay: str, terms: tuple[str, ...]) -> bool:
    return any(term in hay for term in terms)


def topic_of(row) -> str:
    hay = _hay(row)
    category = getattr(row, "category", "") or "Lainnya"
    if _has_any(hay, ("umkm", "usaha mikro")) and category in {"Lainnya", "Ekonomi Jakarta", "Kegiatan KPw DKI"}:
        return "UMKM"
    return TOPIC_BY_CATEGORY.get(category, "Persepsi terhadap BI")


def lexical_voices(row) -> list[str]:
    hay = _hay(row)
    found = [name for name in VOICES if _has_any(hay, VOICE_TERMS[name])]
    return found


def segment_of(row) -> str:
    override = (getattr(row, "segment_override", "") or "").strip()
    if override:
        return override
    hay = _hay(row)
    for name, terms in SEGMENTS:
        if name == "Media":
            continue
        if terms and _has_any(hay, terms):
            return name
    platform = getattr(row, "platform", "")
    if platform == "berita" or getattr(row, "source_tier", 2) == 1:
        return "Media"
    return "segmen tidak teridentifikasi"


def voices_of(row) -> list[str]:
    raw = (getattr(row, "voice_override", "") or "").strip()
    if raw:
        chosen = [item for item in loads(raw) if item in VOICES]
        return chosen
    return lexical_voices(row)


def narrative_of(row) -> str:
    hay = _hay(row)
    for label, groups in NARRATIVES:
        if all(any(term in hay for term in group) for group in groups):
            return label
    return ""


def area_of(row) -> str:
    location = getattr(row, "location", "") or ""
    if location in JAKARTA_AREAS:
        return location
    return ""


def describe_mention(row) -> dict:
    voices = voices_of(row)
    return {
        "voices": voices,
        "voice_labels": [VOICE_LABEL[item] for item in voices],
        "voice_corrected": bool((getattr(row, "voice_override", "") or "").strip()),
        "segment": segment_of(row),
        "segment_corrected": bool((getattr(row, "segment_override", "") or "").strip()),
        "topic": topic_of(row),
        "area": area_of(row) or "wilayah tidak diketahui",
        "narrative": narrative_of(row),
        "method": "Leksikon pada judul dan cuplikan. Bukan profil orang. Lokasi hanya bila nama wilayah sudah tersimpan.",
    }


def _evidence(row) -> dict:
    published = getattr(row, "published_at", None)
    return {
        "id": getattr(row, "id", None),
        "title": getattr(row, "title", ""),
        "url": getattr(row, "url", ""),
        "source": getattr(row, "source_name", ""),
        "published_at": published.isoformat(timespec="minutes") if isinstance(published, datetime) else "",
    }


def _band(high: bool, mid: bool) -> str:
    if high:
        return "Tinggi"
    if mid:
        return "Sedang"
    return "Rendah"


def confidence_of(rows: list) -> str:
    sources = {getattr(row, "source_name", "") for row in rows if getattr(row, "source_name", "")}
    if len(rows) >= 5 and len(sources) >= 3:
        return "Tinggi"
    if len(rows) >= 3 and len(sources) >= 2:
        return "Sedang"
    return "Rendah"


def insufficient(rows: list) -> bool:
    if len(rows) < 3:
        return True
    scores = [getattr(row, "credibility", 60) or 0 for row in rows]
    return bool(scores) and sum(scores) / len(scores) < 40


def lifecycle(rows: list) -> dict:
    ordered = sorted(rows, key=lambda item: item.published_at)
    if len(ordered) < 4 or ordered[0].published_at == ordered[-1].published_at:
        return {
            "tahap": "Muncul",
            "alasan": "Kurang dari 4 konten, atau waktu terbitnya sama. Tahap berkembang, puncak, dan menurun belum bisa dipisah.",
            "eskalasi": False,
            "penanda": "",
        }
    start = ordered[0].published_at
    span = (ordered[-1].published_at - start).total_seconds() or 1
    counts = [0, 0, 0]
    for item in ordered:
        slot = min(2, int((item.published_at - start).total_seconds() / span * 3))
        counts[slot] += 1
    first, mid, last = counts
    if last < mid:
        tahap = "Menurun"
        alasan = f"Bagian akhir {last} konten, lebih sedikit dari bagian tengah {mid}."
    elif last > mid >= first:
        tahap = "Berkembang"
        alasan = f"Jumlah naik dari {first} ke {mid} lalu {last} pada tiga bagian waktu yang sama."
    elif last >= mid and mid >= first:
        tahap = "Puncak"
        alasan = f"Bagian akhir {last} konten masih setinggi atau di atas bagian sebelumnya ({first}, {mid})."
    else:
        tahap = "Muncul"
        alasan = f"Sebaran {first}, {mid}, {last} belum membentuk kenaikan atau penurunan yang jelas."
    neg = sum(1 for row in ordered if row.sentiment == "negatif")
    tier1 = sum(1 for row in ordered if row.source_tier == 1)
    neg_pct = round(neg / len(ordered) * 100)
    eskalasi = tahap in {"Berkembang", "Puncak"} and (neg_pct >= 25 or tier1 >= 1)
    penanda = ""
    if eskalasi:
        penanda = f"Berpotensi eskalasi: {neg_pct}% konten negatif dan {tier1} konten media tier-1. Ambang tampilan, bukan ambang resmi BI."
    return {"tahap": tahap, "alasan": alasan, "eskalasi": eskalasi, "penanda": penanda}


def _impact(rows: list) -> list[dict]:
    total = len(rows) or 1
    neg = sum(1 for row in rows if row.sentiment == "negatif")
    neg_pct = round(neg / total * 100, 1)
    risk = round(sum(getattr(row, "risk_score", 0) or 0 for row in rows) / total, 1)
    tags = sorted({tag for row in rows for tag in loads(getattr(row, "policy_tags", "[]"))})
    relevance = max((getattr(row, "policy_relevance", 0) or 0 for row in rows), default=0)
    kpw = [row for row in rows if getattr(row, "is_kpw", False)]
    kpw_neg = sum(1 for row in kpw if row.sentiment == "negatif")
    tier1 = sum(1 for row in rows if row.source_tier == 1)
    figures = sum(1 for row in rows if getattr(row, "has_public_figure", False))
    velocity = round(sum(getattr(row, "spread_velocity", 0) or 0 for row in rows) / total, 1)
    reputasi = _band(neg_pct >= 40 or risk >= 75, neg_pct >= 25 or risk >= 50)
    if not tags:
        kebijakan = "Rendah"
        alasan_kebijakan = "Tidak ada tag kebijakan pada konten ini."
    else:
        kebijakan = _band(relevance >= 70 and neg_pct >= 25, True)
        alasan_kebijakan = "Tag yang terbaca: " + ", ".join(tags) + f". Relevansi tertinggi {relevance}."
    if not kpw:
        program = "Rendah"
        alasan_program = "Tidak ada konten yang ditandai menyebut program atau kantor KPw."
    else:
        program = _band(kpw_neg / len(kpw) >= 0.4, True)
        alasan_program = f"{len(kpw)} konten menyebut KPw, {kpw_neg} di antaranya negatif."
    eskalasi = _band(velocity >= 50 and (tier1 >= 1 or figures >= 1), velocity >= 30 or tier1 >= 1)
    return [
        {
            "dimensi": "Reputasi dan kepercayaan",
            "tingkat": reputasi,
            "alasan": f"{neg_pct}% konten negatif, rata-rata skor risiko {risk}. Ambang tampilan: 25% sedang, 40% atau risiko 75 tinggi. Bukan ambang resmi BI.",
        },
        {"dimensi": "Keterkaitan kebijakan atau program BI", "tingkat": kebijakan, "alasan": alasan_kebijakan},
        {"dimensi": "Pelaksanaan program KPw DKI", "tingkat": program, "alasan": alasan_program},
        {
            "dimensi": "Potensi eskalasi",
            "tingkat": eskalasi,
            "alasan": f"Kecepatan sebar rata-rata {velocity}. Media tier-1: {tier1}. Konten yang menandai tokoh publik: {figures}. Tokoh tidak diprofilkan.",
        },
    ]


def _triggers(rows: list) -> dict:
    ordered = sorted(rows, key=lambda item: item.published_at)
    first = _evidence(ordered[0])
    first["catatan"] = "Konten paling awal pada kelompok ini. Ini penanda waktu di data, bukan bukti bahwa dialah penyebab."
    hipotesis = []
    hay = " ".join(_hay(row) for row in ordered)
    if any(word in hay for word in ("gagal", "gangguan", "error")) and "penyebab" not in hay:
        hipotesis.append({
            "label": "Hipotesis AI",
            "teks": "Cuplikan memuat kata gangguan atau kegagalan, tetapi tidak menjelaskan penyebabnya. Jangan dibaca sebagai temuan fakta.",
        })
    if not hipotesis:
        hipotesis.append({
            "label": "Hipotesis AI",
            "teks": "Penyebab tidak tertulis pada judul dan cuplikan. Tidak ada dugaan tambahan yang dipaksakan.",
        })
    penguat = []
    tier1 = sorted({row.source_name for row in ordered if row.source_tier == 1})
    if tier1:
        penguat.append("Fakta: media tier-1 yang tersimpan: " + ", ".join(tier1) + ".")
    else:
        penguat.append("Tidak ada media tier-1 pada kelompok ini.")
    seasons = [term for term in SEASON_TERMS if term in hay]
    if seasons:
        penguat.append(
            "Fakta: konten menyebut " + ", ".join(seasons) + ". Itu bukan bukti bahwa kalender adalah penyebab."
        )
    else:
        penguat.append("Tidak ada penyebutan Ramadan, Lebaran, tahun ajaran, atau akhir tahun. Momentum musiman tidak ditebak.")
    return {"pemicu": first, "hipotesis": hipotesis, "penguat": penguat}


def _recommendation(rows: list, voices: Counter) -> dict:
    thin = insufficient(rows)
    keyakinan = confidence_of(rows)
    matched = None
    for rule in SOLUTIONS:
        if not any(name in voices for name in rule["voices"]):
            continue
        hits = [row for row in rows if _has_any(_hay(row), rule["terms"])]
        if hits:
            matched = (rule, hits)
            break
    if matched is None:
        teks = (
            "Data belum cukup, perlu verifikasi"
            if thin
            else "Belum ada keluhan, kebutuhan, atau hoaks yang cocok dengan pola solusi. Pantau dan baca sumber; tidak ada tindakan yang dipaksakan."
        )
        return {
            "jenis": "pantau",
            "teks": teks,
            "urgensi": "Pantau",
            "unit": "Kehumasan",
            "keyakinan": "Rendah" if thin else keyakinan,
            "luar_kewenangan": False,
            "insufficient": thin,
            "alternatif": [{
                "opsi": "Analis membaca tautan satu per satu",
                "tradeoff": "Lebih lambat, tetapi tidak mengunci satu solusi yang belum cocok dengan isi sumber.",
            }],
        }
    rule, hits = matched
    urgensi = "Pantau"
    if not thin and (rule["id"] == "hoaks" or sum(1 for row in hits if row.sentiment == "negatif") >= 3):
        urgensi = "Segera"
    elif not thin and len(hits) >= 3:
        urgensi = "Minggu ini"
    teks = "Data belum cukup, perlu verifikasi" if thin else rule["tindakan"]
    return {
        "jenis": rule["jenis"],
        "teks": teks,
        "urgensi": urgensi,
        "unit": rule["unit"],
        "keyakinan": keyakinan if not thin else "Rendah",
        "luar_kewenangan": rule["luar"],
        "insufficient": thin,
        "alternatif": [
            {
                "opsi": "Tunda dan verifikasi seluruh tautan",
                "tradeoff": "Respons lebih lambat, tetapi menghindari pernyataan yang melebihi bukti.",
            },
            {
                "opsi": rule["tindakan"],
                "tradeoff": "Lebih cepat sampai ke unit terkait, tetapi tetap wajib ditinjau manusia. Tidak ada pesan yang terkirim sendiri.",
            },
        ],
    }


def build_brief(rows: list) -> dict:
    if not rows:
        return {
            "cukup": False,
            "apa": "Data belum cukup, perlu verifikasi",
            "kenapa": {"pemicu": None, "hipotesis": [], "penguat": []},
            "dampak": [],
            "rekomendasi": {"teks": "Data belum cukup, perlu verifikasi", "insufficient": True, "keyakinan": "Rendah"},
            "bukti": [],
            "siklus": {"tahap": "Muncul", "alasan": "Belum ada konten.", "eskalasi": False, "penanda": ""},
            "narasi": [],
            "disclaimer": DISCLAIMER,
        }
    described = [(row, describe_mention(row)) for row in rows]
    voice_counts = Counter(name for _, item in described for name in item["voices"])
    parts = [f"{VOICE_LABEL[name]} {voice_counts[name]}" for name in VOICES if voice_counts[name]]
    apa = (
        f"{len(rows)} konten eksternal. "
        + ("Dimensi yang terbaca: " + ", ".join(parts) + "." if parts else "Belum ada dimensi keluhan, apresiasi, kebutuhan, atau hoaks pada judul dan cuplikan.")
    )
    ordered = sorted(rows, key=lambda item: item.published_at)
    return {
        "cukup": not insufficient(rows),
        "apa": apa,
        "kenapa": _triggers(ordered),
        "dampak": _impact(ordered),
        "rekomendasi": _recommendation(ordered, voice_counts),
        "bukti": [_evidence(row) for row in ordered if getattr(row, "url", "")],
        "siklus": lifecycle(ordered),
        "narasi": _narratives(described),
        "segmen": _count([item["segment"] for _, item in described]),
        "wilayah": _count([item["area"] for _, item in described]),
        "keyakinan": confidence_of(rows),
        "disclaimer": DISCLAIMER,
        "metode": "Apa, kenapa, dampak, dan rekomendasi disusun hanya dari konten eksternal yang tersimpan. Hipotesis tidak dipakai sebagai fakta.",
    }


def _narratives(described: list) -> list[dict]:
    grouped: dict[str, list] = defaultdict(list)
    for row, item in described:
        if item["narrative"]:
            grouped[item["narrative"]].append(row)
    output = []
    for label, members in grouped.items():
        output.append({
            "label": label,
            "jumlah": len(members),
            "sumber": sorted({row.source_name for row in members})[:6],
            "bukti": [_evidence(row) for row in members[:3] if row.url],
        })
    output.sort(key=lambda item: item["jumlah"], reverse=True)
    return output


def _count(values: list[str]) -> list[dict]:
    counts = Counter(values)
    return [{"label": label, "jumlah": counts[label]} for label in counts]


def _match_solution(row, info: dict):
    hay = _hay(row)
    voices = set(info["voices"])
    for rule in SOLUTIONS:
        if not any(name in voices for name in rule["voices"]):
            continue
        if _has_any(hay, rule["terms"]):
            return rule
    return None


def solution_table(rows: list) -> list[dict]:
    grouped: dict[str, list] = defaultdict(list)
    pending = []
    for row in rows:
        info = describe_mention(row)
        if not ({"keluhan", "kebutuhan", "hoaks"} & set(info["voices"])):
            continue
        rule = _match_solution(row, info)
        if rule is None:
            pending.append(row)
        else:
            grouped[rule["id"]].append(row)
    items = []
    for rule in SOLUTIONS:
        members = grouped.get(rule["id"]) or []
        if not members:
            continue
        thin = insufficient(members)
        items.append({
            "id": rule["id"],
            "keluhan": rule["keluhan"],
            "kebutuhan": rule["kebutuhan"],
            "tindakan": "Data belum cukup, perlu verifikasi" if thin else rule["tindakan"],
            "jenis": rule["jenis"],
            "unit": rule["unit"],
            "luar_kewenangan": rule["luar"],
            "urgensi": "Pantau" if thin else ("Segera" if rule["id"] == "hoaks" and len(members) >= 3 else "Minggu ini"),
            "keyakinan": "Rendah" if thin else confidence_of(members),
            "jumlah": len(members),
            "insufficient": thin,
            "bukti": [_evidence(row) for row in members[:5] if row.url],
        })
    if pending:
        items.append({
            "id": "belum-terpetakan",
            "keluhan": "Keluhan atau kebutuhan yang belum cocok dengan pola solusi",
            "kebutuhan": "",
            "tindakan": "Data belum cukup, perlu verifikasi",
            "jenis": "perlu verifikasi",
            "unit": "Kehumasan",
            "luar_kewenangan": False,
            "urgensi": "Pantau",
            "keyakinan": "Rendah",
            "jumlah": len(pending),
            "insufficient": True,
            "bukti": [_evidence(row) for row in pending[:5] if row.url],
        })
    return items


def _ramai_topics(current: list, previous: list) -> set[str]:
    if not previous:
        return set()
    now_counts = Counter(topic_of(row) for row in current)
    then_counts = Counter(topic_of(row) for row in previous)
    chosen = set()
    for topic, count in now_counts.items():
        before = then_counts.get(topic, 0)
        if count < 3:
            continue
        if before == 0 or count >= before * 2:
            chosen.add(topic)
    return chosen


def matches(row, topic: str = "", segment: str = "", area: str = "") -> bool:
    info = describe_mention(row)
    if topic and info["topic"] != topic:
        return False
    if segment and info["segment"] != segment:
        return False
    if area == "tidak-diketahui" and info["area"] != "wilayah tidak diketahui":
        return False
    if area and area != "tidak-diketahui" and info["area"] != area:
        return False
    return True


def snapshot(current: list, previous: list, topic: str = "", segment: str = "", area: str = "") -> dict:
    current_rows = [row for row in current if matches(row, topic, segment, area)]
    previous_rows = [row for row in previous if matches(row, topic, segment, area)]
    ramai = _ramai_topics(current_rows, previous_rows)
    described = []
    for row in current_rows:
        info = describe_mention(row)
        if info["topic"] in ramai:
            info = {**info, "voices": [*info["voices"], "ramai"], "voice_labels": [*info["voice_labels"], VOICE_LABEL["ramai"]]}
        described.append((row, info))
    composition = []
    for key in ("ramai", *VOICES):
        members = [row for row, info in described if key in info["voices"]]
        composition.append({
            "id": key,
            "label": VOICE_LABEL[key],
            "jumlah": len(members),
            "pangsa": round(len(members) / len(described) * 100, 1) if described else 0,
        })
    by_issue: dict[int, list] = defaultdict(list)
    for row, _info in described:
        if getattr(row, "issue_id", None):
            by_issue[row.issue_id].append(row)
    return {
        "total": len(described),
        "komposisi": composition,
        "topik": _count([info["topic"] for _row, info in described]),
        "segmen": _count([info["segment"] for _row, info in described]),
        "wilayah": _count([info["area"] for _row, info in described]),
        "narasi": _narratives(described),
        "topik_ramai": sorted(ramai),
        "siklus_isu": len(by_issue),
        "ramai_tersedia": bool(previous_rows),
        "aturan_ramai": (
            "Topik dihitung ramai bila minimal 3 konten dan jumlahnya minimal dua kali periode sebelumnya. Pangsa dihitung dari konten yang terkumpul, bukan dari seluruh percakapan internet."
            if previous_rows
            else "Ramai belum bisa dihitung: periode sebelumnya belum punya data pembanding. Angka tidak diisi tebakan."
        ),
        "disclaimer": DISCLAIMER,
        "metode": "Dimensi bisa tumpang tindih. Ramai adalah sinyal volume, bukan isi keluhan. Segmen dibaca dari kata di konten, bukan dari identitas akun.",
    }


def tools_map() -> dict:
    return {
        "diadopsi": [
            {
                "teknik": "Pemetaan isu dan titik kesulitan dari percakapan publik",
                "penerapan": "Keluhan, kebutuhan, dan hoaks dibaca dari kata pada judul serta cuplikan, lalu analis dapat mengoreksi.",
                "sumber": "Demos, Poverty and Social Media Listening, 2023",
                "tautan": "https://demos.co.uk/wp-content/uploads/2023/09/Social-Media-Listening_final.pdf",
            },
            {
                "teknik": "Validasi bahwa data media sosial tidak mewakili seluruh penduduk",
                "penerapan": "Angka disebut sebagai pangsa konten yang terkumpul. Survei BI dirujuk, tidak diganti.",
                "sumber": "UK Government, The use of social media for research and analysis, 2014",
                "tautan": "https://assets.publishing.service.gov.uk/media/5a7ecf1ce5274a2e87db20b1/use-of-social-media-for-research-and-analysis.pdf",
            },
            {
                "teknik": "Deteksi lonjakan, narasi keliru, dan kekhawatiran warga",
                "penerapan": "Peringatan Info, Waspada, dan Kritis memakai ambang yang diatur Admin, dengan tautan bukti.",
                "sumber": "Brandwatch, Social listening for government, dokumentasi vendor",
                "tautan": "https://www.brandwatch.com/guides/social-listening-for-government-best-practices/",
            },
            {
                "teknik": "Siklus hidup isu dari volume antarwaktu",
                "penerapan": "Tahap Muncul, Berkembang, Puncak, dan Menurun dihitung dari tiga bagian waktu pada konten tersimpan.",
                "sumber": "Diadaptasi dari pemantauan fase narasi publik. Bukan salinan alat kampanye.",
                "tautan": "https://www.pulsarplatform.com/guides/social-listening-government-public-sector",
            },
        ],
        "ditolak": [
            {
                "teknik": "Microtargeting, profil individu, dan panel orang yang sudah dikenal",
                "alasan": "Melanggar batas UU PDP dan tidak diperlukan untuk persepsi agregat. Dokumentasi vendor yang menawarkan panel konstituen tidak diikuti.",
            },
            {
                "teknik": "Dukungan atau penolakan tokoh dan bahasa kampanye elektoral",
                "alasan": "Bank Indonesia independen dan non-partisan. Narasi yang dipantau hanya persepsi terhadap BI, ekonomi, dan sistem pembayaran.",
            },
            {
                "teknik": "Share of voice sebagai pangsa pasar atau pangsa pemilih",
                "alasan": "Sumber tidak lengkap dan tidak mewakili penduduk. Yang ditampilkan hanya pangsa konten yang berhasil dikumpulkan.",
            },
        ],
        "matriks": [
            {
                "nama": "Contact Center BI BICARA dan pengaduan konsumen",
                "fungsi": "Edukasi, konsultasi, dan fasilitasi pengaduan konsumen sistem pembayaran, layanan uang, serta pasar uang dan valas.",
                "data": "Pengaduan individual. Agregat keluhan tidak ditampilkan pada halaman publik tersebut.",
                "pemilik": "Bank Indonesia. Surat konsumen DKI Jakarta, Bekasi, Bogor, Karawang, dan Depok ditujukan ke KPw BI DKI Jakarta.",
                "kekuatan": "Kanal resmi yang sudah berjalan, dengan alur lapor ke penyelenggara lebih dulu.",
                "batas": "Bukan social listening. Isi pengaduan tidak tersedia di dashboard ini.",
                "posisi": "Melengkapi. Dashboard tidak membangun ulang kanal pengaduan.",
                "status": "Terverifikasi publik",
                "sumber": "https://www.bi.go.id/id/layanan/pengaduan-konsumen/default.aspx",
            },
            {
                "nama": "Survei Konsumen",
                "fungsi": "Keyakinan konsumen atas kondisi ekonomi kini dan ekspektasi 6 bulan ke depan.",
                "data": "Indikator bulanan yang dipublikasikan.",
                "pemilik": "Bank Indonesia. Unit pelaksana di KPw perlu dikonfirmasi.",
                "kekuatan": "Sampel terstruktur, lebih layak dibanding unggahan media untuk menyimpulkan penduduk.",
                "batas": "Bulanan, bukan deteksi percakapan harian.",
                "posisi": "Merujuk. Jangan menduplikasi survei.",
                "status": "Terverifikasi publik",
                "sumber": "https://www.bi.go.id/id/publikasi/laporan/default.aspx",
            },
            {
                "nama": "Survei Penjualan Eceran",
                "fungsi": "Tekanan inflasi dari sisi permintaan dan kecenderungan penjualan eceran.",
                "data": "Indikator bulanan yang dipublikasikan.",
                "pemilik": "Bank Indonesia. Unit pelaksana di KPw perlu dikonfirmasi.",
                "kekuatan": "Mengukur penjualan, bukan opini media.",
                "batas": "Tidak menjelaskan narasi publik.",
                "posisi": "Merujuk. Dashboard hanya menyandingkan persepsi, bila datanya nanti dihubungkan.",
                "status": "Terverifikasi publik",
                "sumber": "https://www.bi.go.id/id/publikasi/laporan/default.aspx",
            },
            {
                "nama": "PIHPS, Pusat Informasi Harga Pangan Strategis",
                "fungsi": "Harga eceran pangan harian di pasar tradisional.",
                "data": "Harga komoditas, disurvei hari kerja pukul 09.00–11.00 WIB, ditargetkan terbit sekitar pukul 13.00 WIB.",
                "pemilik": "Bank Indonesia, bekerja sama dengan pencacah di daerah.",
                "kekuatan": "Harga terukur, sampel kota inflasi BPS, termasuk jaringan nasional.",
                "batas": "Bukan keluhan warga dan bukan peta sentimen.",
                "posisi": "Merujuk. Dashboard tidak menghitung ulang harga.",
                "status": "Terverifikasi publik",
                "sumber": "https://www.bi.go.id/hargapangan/Informasi/FAQ",
            },
            {
                "nama": "Forum TPID",
                "fungsi": "Koordinasi pengendalian inflasi daerah. BI disebut dalam publikasi sebagai bagian dari pembahasan harga pangan daerah.",
                "data": "Tidak ada sistem internal TPID yang terbuka di sumber yang dicek.",
                "pemilik": "Perlu konfirmasi internal: sekretariat TPID DKI dan peran KPw.",
                "kekuatan": "Jalur koordinasi yang sudah dikenal publik.",
                "batas": "Dashboard tidak punya risalah rapat atau keputusan TPID.",
                "posisi": "Melengkapi, hanya bila persepsi harga perlu dibawa ke forum. Tidak menggantikan TPID.",
                "status": "Perlu konfirmasi internal",
                "sumber": "https://www.bi.go.id/hargapangan",
            },
            {
                "nama": "Pemantauan media atau social listening yang sudah dipakai BI",
                "fungsi": "Tidak ditemukan nama sistem, vendor, atau pemiliknya pada sumber publik yang dicek.",
                "data": "Tidak diketahui.",
                "pemilik": "Perlu ditanyakan ke Kehumasan.",
                "kekuatan": "Belum dapat dinilai.",
                "batas": "AI tidak punya akses sistem internal.",
                "posisi": "Belum dapat disebut duplikasi, pelengkap, atau pengganti sebelum tim internal menjawab.",
                "status": "Perlu konfirmasi internal",
                "sumber": "",
            },
        ],
        "pertanyaan": [
            "Tools media monitoring atau social listening apa yang sekarang dipakai, internal atau vendor, dan siapa pemiliknya?",
            "Apakah data pengaduan BI BICARA boleh dipakai dalam bentuk agregat, tanpa identitas pelapor?",
            "Survei atau indikator apa yang rutin dibaca KPw DKI, dan seberapa sering?",
            "Siapa yang membawa hasil Survei Konsumen, Survei Penjualan Eceran, dan PIHPS ke rapat KPw?",
            "Bagaimana alur eskalasi isu dari analis ke pimpinan, dan siapa pengambil keputusan di tiap tingkat?",
            "Siapa juru bicara, berapa tenggat respons, dan seperti apa format klarifikasi hoaks?",
            "Unit mana yang menerima masukan persepsi: Kebijakan Moneter, Sistem Pembayaran, Pengedaran Uang, atau lain?",
            "Apa batasan keamanan data, penyimpanan, dan pengadaan sebelum tools baru boleh dipakai?",
            "Apakah ada daftar kanal resmi BI yang wajib dikecualikan, selain yang sudah diblokir di dashboard?",
            "Bagaimana TPID DKI memakai informasi harga dan keluhan publik hari ini?",
            "Data lokasi mana yang boleh ditampilkan, dan apakah ada wilayah yang tidak boleh ditebak?",
            "Apakah pimpinan ingin ambang Info, Waspada, dan Kritis yang berbeda dari bawaan Admin?",
            "Siapa yang meninjau rekomendasi sebelum materi apa pun keluar dari kantor?",
            "Periode musiman mana yang wajib ditandai manual karena kalender tidak ditebak sistem?",
            "Indikator keberhasilan apa yang dipakai untuk menilai apakah edukasi atau klarifikasi berguna?",
        ],
        "asumsi": [
            "Klasifikasi memakai kata pada judul dan cuplikan, kira-kira 360 karakter, bukan artikel penuh.",
            "Tidak ada akses ke sistem internal BI. Sel yang berstatus Perlu konfirmasi internal memang belum diverifikasi.",
            "Jangkauan dan suka tidak diisi bila sumber tidak menyediakannya.",
            "Ambang dampak dan tahap isu adalah aturan tampilan agar pimpinan punya bahasa yang sama, bukan kebijakan resmi BI.",
            "UU PDP dipakai sebagai batas kerja: data agregat dan publik, tanpa profil individu. Ini bukan pendapat hukum unit hukum BI.",
        ],
        "skoring": [
            "Keyakinan Tinggi: minimal 5 konten dari minimal 3 sumber. Sedang: minimal 3 konten dari minimal 2 sumber. Selain itu Rendah.",
            "Kurang dari 3 konten, atau rata-rata kredibilitas di bawah 40, memunculkan kalimat Data belum cukup, perlu verifikasi.",
            "Reputasi Tinggi bila konten negatif minimal 40% atau rata-rata risiko minimal 75. Sedang bila negatif minimal 25% atau risiko minimal 50.",
            "Ramai: minimal 3 konten dan minimal dua kali jendela sebelumnya.",
            "Hipotesis AI hanya muncul bila penyebab tidak tertulis. Hipotesis tidak masuk ke kalimat fakta.",
        ],
        "disclaimer": DISCLAIMER,
    }


def hoax_hits(rows: list) -> list:
    return [row for row in rows if "hoaks" in voices_of(row)]


def complaint_count(rows: list) -> int:
    return sum(1 for row in rows if "keluhan" in voices_of(row))


def fastest_narrative(current: list, previous: list) -> tuple[str, list]:
    now = Counter(narrative_of(row) for row in current)
    then = Counter(narrative_of(row) for row in previous)
    now.pop("", None)
    best = ""
    best_gain = 0
    for label, count in now.items():
        gain = count - then.get(label, 0)
        if gain > best_gain:
            best = label
            best_gain = gain
    if not best:
        return "", []
    return best, [row for row in current if narrative_of(row) == best]
