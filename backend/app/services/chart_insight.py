"""Generate Insight untuk grafik Ringkasan.

Sistematika 5W1H + tindak lanjut (Now what): Who, What, When, Where, Why, How.
Why wajib kritis dan hanya dari data mention tersimpan (judul, kategori, sumber,
sentimen pada titik relevan)—dilarang mengada-ada insiden. Angka/tautan selalu
dari data. LLM opsional; ditolak bila menambah angka atau penyebab tanpa bukti.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Mention
from app.nlp.voice import VOICE_LABEL, VOICES, _evidence, confidence_of, insufficient, matches, snapshot, topic_of, voices_of
from app.services import analytics
from app.nlp.bi_style import BI_CHART_SUFFIX, BI_VOICE_GUIDE
from app.services.dss_llm import _complete, configured_model

CHARTS = {
    "trend": "Volume mention per waktu",
    "komposisi": "Komposisi sentimen",
    "volume": "Perubahan volume per topik",
    "kata": "Kata yang paling sering muncul",
    "suara": "Komposisi suara publik",
}
GRAIN_LABEL = {"day": "harian", "week": "mingguan", "month": "bulanan"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
THIN = (
    "Data belum memadai untuk simpulan operasional. "
    "Bank Indonesia/KPw BI DKI Jakarta disarankan menunda rekomendasi hingga ambang sumber terpenuhi."
)
WATCH_NEGATIVE = 25.0
INSIGHT_VERSION = "insight-5w1h-1"
WHY_NO_INCIDENT = (
    "Belum ada cukup judul/kategori mention pada titik yang diamati untuk menautkan pola grafik "
    "ke satu insiden atau peristiwa spesifik. Jangan menyimpulkan penyebab tanpa bukti sumber."
)

SYSTEM_PROMPT = f"""Anda membantu tim Kehumasan/KPw BI membaca satu grafik dashboard media monitor.
Susun jawaban 5W1H yang komprehensif, kritis, dan actionable — ragam bahasa Bank Indonesia.

{BI_VOICE_GUIDE}

{BI_CHART_SUFFIX}

Aturan data (mutlak):
- Pakai HANYA angka, tanggal, nama kategori, sumber, lokasi, dan judul yang ada di data JSON.
- Dilarang menambah angka, URL, atau mengarang insiden/peristiwa yang tidak tercantum di data.
- who: siapa aktor/media/kanal yang muncul di data.
- what: apa yang ditunjukkan grafik (fakta kuantitatif).
- when: kapan (rentang + titik puncak/lonjakan bila ada).
- where: di mana (lokasi mention bila ada; jika kosong, nyatakan tidak tercatat).
- why: mengapa pola grafik seperti itu — hanya dari kategori/judul/sumber pada titik relevan.
  Jika data tidak menunjuk satu kejadian, tulis eksplisit bahwa penyebab spesifik belum terbukti.
- how: bagaimana pola terbentuk (lonjakan, pergeseran bertahap, dominasi sentimen, dll.) dari data.
- so_what: implikasi persepsi terhadap mandat BI/KPw (hipotesis, berlabel hati-hati).
- now_what: prioritas tindak lanjut, pemilik, tenggat relatif; bukan keputusan moneter.

Balas hanya JSON dengan kunci: who, what, when, where, why, how, so_what, now_what."""


def _pct(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + "%"


def _signed(value: float, suffix: str = "") -> str:
    text = f"{abs(value):.1f}".replace(".", ",")
    if text.endswith(",0"):
        text = text[:-2]
    return ("+" if value > 0 else "−" if value < 0 else "±") + text + suffix


def _day(key: str, grain: str) -> str:
    parts = key.split("-")
    if grain == "month" and len(parts) == 2:
        return f"{MONTHS[int(parts[1]) - 1]} {parts[0]}"
    if len(parts) == 3:
        label = f"{int(parts[2])} {MONTHS[int(parts[1]) - 1]}"
        return f"pekan {label}" if grain == "week" else label
    return key


def _bucket_rows(rows: list[Mention], key: str, grain: str) -> list[Mention]:
    return [row for row in rows if analytics._bucket(row.published_at, grain) == key]


def _top(rows: list[Mention], limit: int = 3) -> list[dict]:
    ordered = sorted(rows, key=lambda row: (row.risk_score, row.reach_estimate), reverse=True)
    return [_evidence(row) for row in ordered if (row.url or "").startswith("http")][:limit]


def _main_category(rows: list[Mention]) -> tuple[str, int]:
    counts = Counter(row.category or "Lainnya" for row in rows)
    return counts.most_common(1)[0] if counts else ("", 0)


def _trend(db: Session, window: dict, grain: str) -> dict:
    rows = analytics.base_query(db, window).all()
    previous = analytics.base_query(db, analytics.previous_window(window)).count()
    points = analytics.trend(db, window, grain)
    total = len(rows)
    facts = {"total": total, "periode_lalu": previous, "titik": len(points), "granularitas": GRAIN_LABEL[grain]}
    if not points:
        return {
            "rows": rows,
            "focus_rows": [],
            "facts": facts,
            "evidence": [],
            "what": "Belum ada mention pada rentang ini.",
            "so": THIN,
            "now": THIN,
            "how": "Tidak ada titik data pada grafik untuk dibaca.",
        }

    peak = max(points, key=lambda item: item["total"])
    peak_rows = _bucket_rows(rows, peak["date"], grain)
    peak_neg = round(peak["negatif"] / peak["total"] * 100, 1) if peak["total"] else 0.0
    half = len(points) // 2
    first = points[:half] or points
    second = points[half:]
    avg_first = sum(item["total"] for item in first) / len(first)
    avg_second = sum(item["total"] for item in second) / len(second)
    if avg_second > avg_first * 1.2:
        direction = "naik"
    elif avg_second < avg_first * 0.8:
        direction = "turun"
    else:
        direction = "relatif stabil"
    spikes = [item for item in points if item["spike"]]
    peak_cat, peak_cat_n = _main_category(peak_rows)
    facts.update(
        {
            "puncak": _day(peak["date"], grain),
            "puncak_jumlah": peak["total"],
            "puncak_negatif_pct": peak_neg,
            "puncak_kategori": peak_cat,
            "rata_paruh_awal": round(avg_first, 1),
            "rata_paruh_akhir": round(avg_second, 1),
            "arah": direction,
            "lonjakan": [_day(item["date"], grain) for item in spikes],
        }
    )

    what = (
        f"Ada {total} mention dalam {len(points)} titik {GRAIN_LABEL[grain]}. "
        f"Puncak pada {_day(peak['date'], grain)} dengan {peak['total']} mention, {_pct(peak_neg)} di antaranya negatif. "
        f"Rata-rata per titik {direction}: {str(round(avg_first, 1)).replace('.', ',')} pada paruh awal, "
        f"{str(round(avg_second, 1)).replace('.', ',')} pada paruh akhir."
    )
    if previous:
        delta = analytics._delta_pct(total, previous) or 0.0
        what += f" Dibanding periode sebelumnya ({previous} mention), volume {_signed(delta, '%')}."
        facts["perubahan_pct"] = delta
    else:
        what += " Periode sebelumnya belum punya data, jadi perbandingan belum bisa dihitung."

    critical = peak_neg >= 40
    if peak_neg >= 40:
        so = f"Puncak pada {_day(peak['date'], grain)} didorong nada negatif ({_pct(peak_neg)}), terutama kategori {peak_cat}. Berpotensi memengaruhi persepsi terhadap mandat BI."
        now = (
            f"Kehumasan meninjau sumber puncak {_day(peak['date'], grain)} dan menyiapkan opsi klarifikasi media sosial atau keterangan pers. "
            "KRITIS: hindari menunggu bila media tier-1 ikut membawa narasi downside."
        )
    elif spikes or direction == "naik":
        so = f"Volume {direction}; kategori {peak_cat} memimpini puncak ({peak_cat_n}/{peak['total']} mention). Momentum perlu dipantau terhadap kredibilitas komunikasi BI."
        now = f"Pantau kategori {peak_cat}. Siapkan rancangan edukasi/penjelasan bila porsi negatif melampaui {_pct(WATCH_NEGATIVE)}."
    else:
        so = "Pola volume relatif stabil; belum terdeteksi lonjakan yang mengarah ke eskalasi reputasi."
        now = "Lanjutkan pemantauan rutin sesuai siklus KPw. Tidak ada respons wajib tanpa temuan downside baru."
    if spikes:
        how = (
            f"Pola terbentuk lewat lonjakan pada {', '.join(_day(item['date'], grain) for item in spikes[:3])}; "
            f"arah paruh akhir {direction}."
        )
    else:
        how = f"Pola terbentuk tanpa penanda lonjakan otomatis; arah volume paruh akhir {direction}."
    return {
        "rows": rows,
        "focus_rows": peak_rows,
        "facts": facts,
        "evidence": _top(peak_rows),
        "what": what,
        "so": so,
        "now": now,
        "how": how,
        "critical": critical,
        "when_focus": facts.get("puncak", ""),
    }


def _komposisi(db: Session, window: dict) -> dict:
    rows = analytics.base_query(db, window).all()
    prev_rows = analytics.base_query(db, analytics.previous_window(window)).all()
    share = analytics._sentiment_share(rows)
    prev = analytics._sentiment_share(prev_rows)
    negatives = [row for row in rows if row.sentiment == "negatif"]
    neg_cat, neg_cat_n = _main_category(negatives)
    facts = {
        "total": len(rows),
        "positif_pct": share["positif"],
        "netral_pct": share["netral"],
        "negatif_pct": share["negatif"],
        "jumlah_negatif": len(negatives),
        "kategori_negatif_utama": neg_cat,
        "periode_lalu": len(prev_rows),
    }
    what = (
        f"Dari {len(rows)} mention: positif {_pct(share['positif'])}, netral {_pct(share['netral'])}, "
        f"negatif {_pct(share['negatif'])}."
    )
    neg_delta: Optional[float] = None
    if prev_rows:
        neg_delta = round(share["negatif"] - prev["negatif"], 1)
        facts.update({"negatif_lalu_pct": prev["negatif"], "perubahan_negatif_poin": neg_delta})
        what += f" Periode lalu negatif {_pct(prev['negatif'])} dari {len(prev_rows)} mention ({_signed(neg_delta, ' poin')})."
    else:
        what += " Periode lalu belum punya data pembanding."

    if negatives:
        so = f"Nada negatif terutama datang dari kategori {neg_cat} ({neg_cat_n} dari {len(negatives)} mention negatif)."
    else:
        so = "Belum ada mention bernada negatif pada rentang ini."
    if share["negatif"] >= WATCH_NEGATIVE:
        so += f" Porsi negatif sudah melewati ambang pantau {_pct(WATCH_NEGATIVE)}."
    rising = neg_delta is not None and neg_delta >= 5
    critical = share["negatif"] >= WATCH_NEGATIVE or rising
    if share["negatif"] >= WATCH_NEGATIVE or rising:
        now = (
            f"Tinjau {len(negatives)} konten negatif (kategori utama {neg_cat}). "
            "Susun draf klarifikasi bila ada fakta keliru. KRITIS bila hoaks mengatasnamakan BI."
        )
    else:
        now = "Komposisi sentimen masih dalam ambang pantau. Konten positif dapat dipertimbangkan untuk amplifikasi edukasi setelah persetujuan pimpinan."
    evidence = _top(negatives) or _top(rows)
    how = (
        f"Komposisi terbentuk dari {len(rows)} mention tersimpan; "
        f"porsi negatif {_pct(share['negatif'])}"
        + (f" berubah {_signed(neg_delta, ' poin')} vs periode lalu." if neg_delta is not None else " tanpa baseline periode lalu.")
    )
    return {
        "rows": rows,
        "focus_rows": negatives or rows,
        "facts": facts,
        "evidence": evidence,
        "what": what,
        "so": so,
        "now": now,
        "how": how,
        "critical": critical,
    }


def _volume(db: Session, window: dict) -> dict:
    rows = analytics.base_query(db, window).all()
    shift = analytics.category_shift(db, window)
    previous_total = sum(item["previous"] for item in shift)
    up = max(shift, key=lambda item: item["delta"], default=None)
    down = min(shift, key=lambda item: item["delta"], default=None)
    facts = {"total": len(rows), "periode_lalu": previous_total, "kategori": shift[:6]}
    if not shift or (up and up["delta"] == 0 and down and down["delta"] == 0):
        return {
            "rows": rows,
            "focus_rows": rows,
            "facts": facts,
            "evidence": _top(rows),
            "what": "Volume per kategori tidak berubah dibanding periode lalu.",
            "so": "Belum ada pergeseran topik yang perlu dibaca.",
            "now": "Lanjutkan pemantauan rutin.",
            "how": "Tidak ada delta kategori yang signifikan pada grafik.",
        }

    what = f"Kenaikan terbesar pada {up['category']} ({_signed(up['delta'])} mention, dari {up['previous']} ke {up['current']})."
    if down and down["delta"] < 0:
        what += f" Penurunan terbesar pada {down['category']} ({_signed(down['delta'])} mention, dari {down['previous']} ke {down['current']})."
    no_baseline = not previous_total
    if no_baseline:
        what += " Periode lalu kosong, jadi selisih sama dengan jumlah periode ini."

    up_rows = [row for row in rows if (row.category or "Lainnya") == up["category"]]
    up_neg = analytics._sentiment_share(up_rows)["negatif"] if up_rows else 0.0
    facts.update({"naik_terbesar": up["category"], "naik_negatif_pct": up_neg})
    critical = up_neg >= 40
    if up_neg >= 40:
        so = f"Kenaikan kategori {up['category']} disertai nada negatif {_pct(up_neg)} — berpotensi menyesatkan persepsi kebijakan/sistem pembayaran."
        now = f"Konsolidasi isu {up['category']} dan verifikasi bukti. Koordinasi Kehumasan–Unit terkait sebelum keterangan resmi."
    else:
        so = f"Prioritas perhatian publik bergeser ke {up['category']} (negatif {_pct(up_neg)})."
        now = f"Pantau {up['category']}; siapkan materi edukasi BI bila relevan dengan mandat KPw."
    how = (
        f"Pergeseran terbaca dari selisih volume kategori: {up['category']} "
        f"{_signed(up['delta'])} mention (dari {up['previous']} ke {up['current']})."
    )
    return {
        "rows": rows,
        "focus_rows": up_rows,
        "facts": facts,
        "evidence": _top(up_rows),
        "what": what,
        "so": so,
        "now": now,
        "how": how,
        "no_baseline": no_baseline,
        "critical": critical,
    }


def _kata(db: Session, window: dict) -> dict:
    rows = analytics.base_query(db, window).all()
    words = analytics.topics(db, window)["words"][:3]
    facts = {"total": len(rows), "kata_teratas": words}
    if not words:
        return {
            "rows": rows,
            "focus_rows": [],
            "facts": facts,
            "evidence": [],
            "what": "Belum ada kata yang cukup sering muncul pada rentang ini.",
            "so": THIN,
            "now": THIN,
            "how": "Frekuensi kata belum membentuk puncak yang dapat dibaca.",
        }

    top = words[0]["text"]
    holders = [row for row in rows if top in f"{row.title} {row.text}".casefold()]
    related = [item["text"] for item in analytics.related_words(db, window, top)[:3]]
    neg = analytics._sentiment_share(holders)["negatif"] if holders else 0.0
    cat, cat_n = _main_category(holders)
    facts.update({"kata_utama": top, "memuat_kata": len(holders), "negatif_pct": neg, "kategori": cat, "kata_terkait": related})

    listed = ", ".join(f"{item['text']} ({item['value']} kali)" for item in words)
    what = f"Dari {len(rows)} mention, kata yang paling sering muncul: {listed}."
    if related:
        what += f" Kata {top} paling sering muncul bersama {', '.join(related)}."
    so = f"Percakapan berpusat pada {top}, terutama kategori {cat} ({cat_n} dari {len(holders)} mention yang memuat kata itu). Nada negatifnya {_pct(neg)}."
    critical = neg >= 40
    if neg >= 40:
        so += " Frasa ini berpotensi menjadi isu reputasi; perlu pembacaan hati-hati terhadap konteks kebijakan."
        now = (
            f"Lacak frasa «{top}» di Jelajah Berita. KRITIS: susun klarifikasi bila hoaks atau simplifikasi kebijakan moneter."
        )
    else:
        now = f"Pantau «{top}» pada siklus berikutnya. Belum ada respons wajib tanpa peningkatan nada negatif."
    how = (
        f"Konsentrasi wacana terbentuk karena frasa «{top}» muncul di {len(holders)} dari {len(rows)} mention"
        + (f", sering bersama {', '.join(related)}." if related else ".")
    )
    return {
        "rows": holders or rows,
        "focus_rows": holders,
        "facts": facts,
        "evidence": _top(holders),
        "what": what,
        "so": so,
        "now": now,
        "how": how,
        "cap": True,
        "critical": critical,
    }


def _suara(db: Session, window: dict, topic: str, segment: str, area: str) -> dict:
    current = analytics.base_query(db, window).all()
    previous = analytics.base_query(db, analytics.previous_window(window)).all()
    snap = snapshot(current, previous, topic, segment, area)
    rows = [row for row in current if matches(row, topic, segment, area)]
    counts = {item["id"]: item for item in snap["komposisi"]}
    facts = {"total": snap["total"], "komposisi": snap["komposisi"], "ramai_tersedia": snap["ramai_tersedia"], "filter": {"topik": topic, "segmen": segment, "wilayah": area}}
    if not rows:
        return {
            "rows": rows,
            "focus_rows": [],
            "facts": facts,
            "evidence": [],
            "what": "Belum ada konten eksternal untuk pilihan ini.",
            "so": THIN,
            "now": THIN,
            "how": "Filter tidak menghasilkan konten yang dapat diurai.",
        }

    parts = [f"{VOICE_LABEL[key].lower()} {counts[key]['jumlah']} ({_pct(counts[key]['pangsa'])})" for key in VOICES]
    what = f"Dari {snap['total']} konten: " + ", ".join(parts) + "."
    if snap["ramai_tersedia"]:
        what += f" Ramai {counts['ramai']['jumlah']} konten ({_pct(counts['ramai']['pangsa'])})."
    else:
        what += " Ramai belum bisa dihitung karena periode lalu belum punya data."

    members = {key: [row for row in rows if key in voices_of(row)] for key in VOICES}
    dominant = max(VOICES, key=lambda key: len(members[key]))
    if not members[dominant]:
        so = "Belum ada keluhan, apresiasi, kebutuhan, atau hoaks yang terbaca dari kata pada konten."
        now = "Lanjutkan pemantauan. Koreksi label di Jelajah Berita bila ada yang terlewat."
        return {
            "rows": rows,
            "focus_rows": rows,
            "facts": facts,
            "evidence": _top(rows),
            "what": what,
            "so": so,
            "now": now,
            "how": "Dimensi suara belum terisi dari pola kata otomatis.",
            "cap": True,
        }

    focus = "hoaks" if members["hoaks"] else dominant
    focus_rows = members[focus]
    main_topic = Counter(topic_of(row) for row in members[dominant]).most_common(1)[0][0]
    facts.update({"suara_dominan": VOICE_LABEL[dominant], "topik_dominan": main_topic})
    so = f"Suara yang paling banyak terbaca adalah {VOICE_LABEL[dominant].lower()} ({len(members[dominant])} konten), terutama topik {main_topic}."
    critical = bool(members["hoaks"])
    if members["hoaks"]:
        so += f" Terdapat {len(members['hoaks'])} konten berpola hoaks — risiko kredibilitas kanal resmi Bank Indonesia."
        now = "KRITIS: verifikasi hoaks dengan Unit Hukum; siapkan klarifikasi kanal resmi dalam 24 jam setelah fakta lengkap."
    elif dominant == "keluhan":
        now = f"Koordinasi unit terkait topik {main_topic} untuk merespons keluhan publik. Sampaikan persepsi, bukan perubahan kebijakan moneter."
    elif dominant == "kebutuhan":
        now = f"Siapkan bahan edukasi {main_topic} ragam BI untuk ditinjau Kehumasan/KPw sebelum dipublikasikan."
    else:
        now = "Pertimbangkan amplifikasi apresiasi pada kanal resmi setelah persetujuan pimpinan."
    how = (
        f"Dimensi {VOICE_LABEL[focus].lower()} mengisi {len(focus_rows)} konten dari filter aktif; "
        f"suara dominan keseluruhan {VOICE_LABEL[dominant].lower()}."
    )
    return {
        "rows": rows,
        "focus_rows": focus_rows,
        "facts": facts,
        "evidence": _top(focus_rows),
        "what": what,
        "so": so,
        "now": now,
        "how": how,
        "cap": True,
        "critical": critical,
    }


def _numbers(text: str) -> set[str]:
    found = set()
    for item in re.findall(r"\d+(?:[.,]\d+)?", text):
        value = item.replace(",", ".")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        found.add(value)
    return found


def _who(rows: list[Mention]) -> str:
    if not rows:
        return "Belum ada aktor/media yang tercatat pada filter grafik ini."
    sources = Counter((row.source_name or "Tidak diketahui").strip() or "Tidak diketahui" for row in rows)
    platforms = Counter((row.platform or "lainnya").strip() or "lainnya" for row in rows)
    top_sources = ", ".join(f"{name} ({count})" for name, count in sources.most_common(4))
    top_platforms = ", ".join(f"{name} ({count})" for name, count in platforms.most_common(3))
    return (
        f"Aktor yang muncul di data: sumber {top_sources}. "
        f"Kanal/platform: {top_platforms}. "
        "Ini identitas penerbit/kanal tersimpan—bukan profil orang."
    )


def _when(window: dict, facts: dict, grain: str = "day") -> str:
    period = f"{window['date_from'].isoformat()} s.d. {window['date_to'].isoformat()}"
    parts = [f"Rentang pantauan: {period}."]
    if facts.get("puncak"):
        parts.append(
            f"Titik puncak volume: {facts['puncak']}"
            + (f" ({facts.get('puncak_jumlah')} mention)." if facts.get("puncak_jumlah") is not None else ".")
        )
    if facts.get("lonjakan"):
        parts.append(f"Penanda lonjakan otomatis: {', '.join(facts['lonjakan'][:4])}.")
    if facts.get("granularitas"):
        parts.append(f"Granularitas grafik: {facts['granularitas']}.")
    elif grain:
        parts.append(f"Granularitas grafik: {GRAIN_LABEL.get(grain, grain)}.")
    return " ".join(parts)


def _where(rows: list[Mention]) -> str:
    locations = Counter(
        (row.location or "").strip()
        for row in rows
        if (row.location or "").strip() and (row.location or "").strip().casefold() not in {"", "-", "tidak diketahui"}
    )
    if not locations:
        return (
            "Lokasi geografis mention tidak tercatat pada sebagian besar data filter ini. "
            "Jangan mengisi wilayah dari asumsi."
        )
    listed = ", ".join(f"{name} ({count})" for name, count in locations.most_common(5))
    return f"Lokasi yang tercatat di data: {listed}."


def _why(focus_rows: list[Mention], context: str) -> str:
    """Why kritis: hanya dari judul/kategori/sumber fokus — tanpa mengarang insiden."""
    if not focus_rows:
        return WHY_NO_INCIDENT
    cat, cat_n = _main_category(focus_rows)
    sources = Counter((row.source_name or "Tidak diketahui") for row in focus_rows).most_common(3)
    sentiments = Counter((row.sentiment or "netral") for row in focus_rows)
    ordered = sorted(focus_rows, key=lambda row: (row.risk_score, row.reach_estimate), reverse=True)
    titles = [((row.title or "").strip()) for row in ordered if (row.title or "").strip()][:4]
    parts = [
        f"Pembacaan kritis penyebab pola grafik pada {context}: "
        f"dari {len(focus_rows)} mention fokus, kategori dominan {cat or 'Lainnya'} ({cat_n} mention)."
    ]
    if sources:
        parts.append("Sumber yang paling sering pada titik ini: " + ", ".join(f"{name} ({count})" for name, count in sources) + ".")
    if sentiments:
        mood = ", ".join(f"{name} {count}" for name, count in sentiments.most_common())
        parts.append(f"Komposisi nada pada titik fokus: {mood}.")
    if titles:
        quoted = "; ".join(f"«{title}»" for title in titles[:3])
        parts.append(f"Judul berisiko/tinggi jangkauan yang tercatat: {quoted}.")
        parts.append(
            "Judul di atas adalah sinyal dari data tersimpan, bukan konfirmasi resmi bahwa satu insiden tunggal "
            "telah diverifikasi Bank Indonesia. Hubungkan ke peristiwa hanya setelah bukti sumber dibuka."
        )
    else:
        parts.append(WHY_NO_INCIDENT)
    return " ".join(parts)


def _build_5w1h(window: dict, chart: str, result: dict, grain: str) -> dict:
    rows = result.get("rows") or []
    focus = result.get("focus_rows") or rows
    facts = result.get("facts") or {}
    context = {
        "trend": f"titik puncak {facts.get('puncak') or 'periode ini'}",
        "komposisi": "mention bernada negatif / keseluruhan periode",
        "volume": f"kategori {facts.get('naik_terbesar') or 'yang naik'}",
        "kata": f"mention yang memuat frasa «{facts.get('kata_utama') or '-'}»",
        "suara": f"dimensi suara {facts.get('suara_dominan') or 'terfilter'}",
    }.get(chart, "periode filter")
    return {
        "who": _who(focus or rows),
        "what": (result.get("what") or "").strip(),
        "when": _when(window, facts, grain),
        "where": _where(focus or rows),
        "why": _why(focus, context),
        "how": (result.get("how") or "Pola dibaca dari agregasi data grafik tersimpan.").strip(),
        "so": (result.get("so") or "").strip(),
        "now": (result.get("now") or "").strip(),
    }


def _llm(chart: str, facts: dict, base: dict) -> Optional[dict]:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return None
    # Sertakan ringkasan 5W1H faktual agar model tidak mengarang Why.
    payload = json.dumps(
        {
            "grafik": CHARTS[chart],
            "data": facts,
            "fakta_5w1h": {
                "who": base.get("who"),
                "what": base.get("what"),
                "when": base.get("when"),
                "where": base.get("where"),
                "why": base.get("why"),
                "how": base.get("how"),
                "so_what": base.get("so"),
                "now_what": base.get("now"),
            },
            "aturan_why": "Why hanya boleh memparafrase fakta_5w1h.why; dilarang menambah insiden baru.",
        },
        ensure_ascii=False,
        default=str,
    )
    raw = _complete(SYSTEM_PROMPT, payload, key)
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    keys = ("who", "what", "when", "where", "why", "how", "so_what", "now_what")
    parts = {key: str(data.get(key) or "").strip() for key in keys}
    # Minimal What + Why + Now harus ada; kunci lain boleh diisi dari base.
    if not parts["what"] or not parts["why"] or not parts["now_what"]:
        return None
    blob = " ".join(parts.values())
    if re.search(r"https?://|www\.", blob):
        return None
    allowed = _numbers(payload + " " + (base.get("what") or "") + " " + (base.get("why") or ""))
    if not _numbers(blob) <= allowed:
        return None
    # Tolak Why yang menambahkan klaim insiden tanpa jejak di fakta dasar.
    why_folded = parts["why"].casefold()
    base_why = (base.get("why") or "").casefold()
    invent_markers = ("insiden besar", "kerusuhan", "bom", "pembunuhan", "skandal rahasia")
    if any(marker in why_folded and marker not in base_why for marker in invent_markers):
        return None
    return {
        "who": parts["who"] or base.get("who", ""),
        "what": parts["what"],
        "when": parts["when"] or base.get("when", ""),
        "where": parts["where"] or base.get("where", ""),
        "why": parts["why"],
        "how": parts["how"] or base.get("how", ""),
        "so": parts["so_what"] or base.get("so", ""),
        "now": parts["now_what"],
    }


def _cap(level: str, no_baseline: bool) -> str:
    return "Sedang" if no_baseline and level == "Tinggi" else level


_THIN_NOW = (
    "Tunda rekomendasi komunikasi. Perluas rentang tanggal atau perbarui data, lalu ulangi Generate Insight "
    "setelah ambang sumber terpenuhi."
)


def _apply_bi_voice(chart: str, sections: dict, *, thin: bool, critical: bool) -> dict:
    what = (sections.get("what") or "").strip()
    so = (sections.get("so") or "").strip()
    now = (sections.get("now") or "").strip()
    who = (sections.get("who") or "").strip()
    when = (sections.get("when") or "").strip()
    where = (sections.get("where") or "").strip()
    why = (sections.get("why") or "").strip()
    how = (sections.get("how") or "").strip()
    if thin:
        return {
            "who": who or "Data aktor belum memadai.",
            "what": what or "Data grafik belum memadai.",
            "when": when or "Rentang belum bisa dibaca.",
            "where": where or "Lokasi belum tercatat.",
            "why": WHY_NO_INCIDENT,
            "how": how or "Pola belum terbentuk.",
            "so": THIN,
            "now": _THIN_NOW,
        }
    prefix = {
        "trend": "Ringkasan eksekutif — dinamika volume mention. ",
        "kata": "Isu & tren — konsentrasi wacana. ",
        "komposisi": "Pemantauan nada publik — komposisi sentimen. ",
        "volume": "Pergeseran topik — perubahan volume per rubrik. ",
        "suara": "Suara publik — keluhan, kebutuhan, hoaks, dan apresiasi. ",
    }.get(chart, "")
    krit = ""
    if critical:
        if chart == "suara":
            krit = "Hoaks/risiko tinggi terdeteksi — "
        elif chart == "trend":
            krit = "Prioritas tinggi (≤24 jam setelah verifikasi): "
        else:
            krit = "Ambang kritis terlampaui — "
    why_out = (
        f"{why} "
        "Evaluasi kritis: bedakan korelasi judul/kategori dengan klaim sebab-akibat; "
        "tanpa bukti sumber, jangan menyimpulkan ada insiden tunggal."
    )
    so_out = (
        f"Implikasi persepsi (hipotesis): {so} "
        "Wajib diverifikasi manusia sebelum menjadi dasar pernyataan resmi."
    )
    return {
        "who": who,
        "what": f"{prefix}{what}".strip(),
        "when": when,
        "where": where,
        "why": why_out,
        "how": how,
        "so": so_out,
        "now": f"{krit}{now}".strip(),
    }


def generate(db: Session, window: dict, chart: str, grain: str = "day", topic: str = "", segment: str = "", area: str = "") -> dict:
    if chart == "trend":
        result = _trend(db, window, grain)
    elif chart == "komposisi":
        result = _komposisi(db, window)
    elif chart == "kata":
        result = _kata(db, window)
    elif chart == "suara":
        result = _suara(db, window, topic, segment, area)
    else:
        result = _volume(db, window)
    rows = result["rows"]
    thin = insufficient(rows)
    sections = _build_5w1h(window, chart, result, grain)
    used_llm = False
    if not thin:
        # Facts untuk LLM juga membawa cuplikan judul fokus (terbatas) agar Why tetap berbasis data.
        focus = result.get("focus_rows") or []
        title_samples = [((row.title or "").strip())[:140] for row in focus[:5] if (row.title or "").strip()]
        facts = dict(result["facts"])
        facts["judul_fokus"] = title_samples
        rewritten = _llm(chart, facts, sections)
        if rewritten:
            sections = rewritten
            used_llm = True
    critical = bool(result.get("critical"))
    sections = _apply_bi_voice(chart, sections, thin=thin, critical=critical)
    method = f"Ragam Bank Indonesia · 5W1H · {INSIGHT_VERSION}"
    if used_llm:
        method += f" · model {configured_model()} (angka & Why diperiksa)"
    else:
        method += " · disusun dari data grafik + judul mention fokus"
    return {
        "chart": chart,
        "title": CHARTS[chart],
        "period": {"from": window["date_from"].isoformat(), "to": window["date_to"].isoformat()},
        "who": sections["who"],
        "what": sections["what"],
        "when": sections["when"],
        "where": sections["where"],
        "why": sections["why"],
        "how": sections["how"],
        "what_happened": sections["what"],
        "so_what": sections["so"],
        "now_what": sections["now"],
        "keyakinan": "Rendah" if thin else _cap(confidence_of(rows), result.get("no_baseline", False) or result.get("cap", False)),
        "insufficient": thin,
        "evidence": result["evidence"],
        "method": method,
        "insight_version": INSIGHT_VERSION,
        "framework": "5W1H",
    }
