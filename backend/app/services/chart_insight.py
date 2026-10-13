"""Generate Insight untuk grafik Ringkasan.

Sistematika mengikuti EWS REGINA: What happened (fakta dari grafik), So what
(interpretasi, berlabel Hipotesis AI), Now what (saran untuk ditinjau manusia),
lalu tingkat keyakinan. Angka dan tautan selalu dari data tersimpan. Model bahasa
hanya dipakai bila LLM_API_KEY ada, dan keluarannya ditolak bila memuat angka
atau tautan yang tidak ada di ringkasan grafik.
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
THIN = "Data belum cukup, perlu verifikasi."
WATCH_NEGATIVE = 25.0

SYSTEM_PROMPT = """Anda membantu tim kehumasan Bank Indonesia membaca satu grafik dashboard.
Tulis dalam Bahasa Indonesia formal dan netral, masing-masing satu sampai dua kalimat.
Aturan:
- Pakai hanya angka, tanggal, dan nama kategori yang ada di data. Jangan menambah angka.
- Jangan menulis URL, nama media, atau kutipan.
- so_what adalah hipotesis, bukan fakta. now_what adalah saran untuk ditinjau pimpinan, bukan keputusan.
- Jangan menyarankan publikasi otomatis. Ini masukan persepsi publik, bukan kebijakan moneter.
Balas hanya JSON dengan kunci: what_happened, so_what, now_what."""


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
        return {"rows": rows, "facts": facts, "evidence": [], "what": "Belum ada mention pada rentang ini.", "so": THIN, "now": THIN}

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

    if peak_neg >= 40:
        so = f"Puncak pada {_day(peak['date'], grain)} didorong nada negatif, terutama kategori {peak_cat}. Kemungkinan ada pemberitaan yang memancing kritik."
        now = f"Baca sumber pada {_day(peak['date'], grain)} di daftar bukti, lalu nilai perlu tidaknya klarifikasi. Keputusan tetap pada pimpinan."
    elif spikes or direction == "naik":
        so = f"Perhatian publik menguat; kategori {peak_cat} paling banyak muncul pada puncak ({peak_cat_n} dari {peak['total']} mention). Nada belum didominasi negatif."
        now = f"Pantau kategori {peak_cat} pada pembaruan berikutnya. Siapkan bahan penjelasan bila porsi negatif mulai naik."
    else:
        so = "Percakapan relatif stabil. Belum terlihat tanda eskalasi dari pola volume."
        now = "Lanjutkan pemantauan rutin. Tidak ada tindakan yang dipaksakan."
    return {"rows": rows, "facts": facts, "evidence": _top(peak_rows), "what": what, "so": so, "now": now}


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
    if share["negatif"] >= WATCH_NEGATIVE or rising:
        now = f"Tinjau berita negatif teratas kategori {neg_cat} di daftar bukti. Siapkan bahan klarifikasi bila ada fakta keliru, untuk diputuskan pimpinan."
    else:
        now = "Komposisi masih aman. Berita positif bisa jadi bahan komunikasi setelah disetujui pimpinan."
    evidence = _top(negatives) or _top(rows)
    return {"rows": rows, "facts": facts, "evidence": evidence, "what": what, "so": so, "now": now}


def _volume(db: Session, window: dict) -> dict:
    rows = analytics.base_query(db, window).all()
    shift = analytics.category_shift(db, window)
    previous_total = sum(item["previous"] for item in shift)
    up = max(shift, key=lambda item: item["delta"], default=None)
    down = min(shift, key=lambda item: item["delta"], default=None)
    facts = {"total": len(rows), "periode_lalu": previous_total, "kategori": shift[:6]}
    if not shift or (up and up["delta"] == 0 and down and down["delta"] == 0):
        return {"rows": rows, "facts": facts, "evidence": _top(rows), "what": "Volume per kategori tidak berubah dibanding periode lalu.", "so": "Belum ada pergeseran topik yang perlu dibaca.", "now": "Lanjutkan pemantauan rutin."}

    what = f"Kenaikan terbesar pada {up['category']} ({_signed(up['delta'])} mention, dari {up['previous']} ke {up['current']})."
    if down and down["delta"] < 0:
        what += f" Penurunan terbesar pada {down['category']} ({_signed(down['delta'])} mention, dari {down['previous']} ke {down['current']})."
    no_baseline = not previous_total
    if no_baseline:
        what += " Periode lalu kosong, jadi selisih sama dengan jumlah periode ini."

    up_rows = [row for row in rows if (row.category or "Lainnya") == up["category"]]
    up_neg = analytics._sentiment_share(up_rows)["negatif"] if up_rows else 0.0
    facts.update({"naik_terbesar": up["category"], "naik_negatif_pct": up_neg})
    if up_neg >= 40:
        so = f"Kenaikan {up['category']} disertai nada negatif {_pct(up_neg)}. Topik ini berpotensi menjadi isu."
        now = f"Buka isu {up['category']} dan baca sumber di daftar bukti. Nilai perlu tidaknya penjelasan, keputusan pada pimpinan."
    else:
        so = f"Perhatian bergeser ke {up['category']}; nada negatifnya {_pct(up_neg)}, belum dominan."
        now = f"Pantau {up['category']} pada pembaruan berikutnya. Bila relevan, siapkan bahan edukasi untuk ditinjau."
    return {"rows": rows, "facts": facts, "evidence": _top(up_rows), "what": what, "so": so, "now": now, "no_baseline": no_baseline}


def _kata(db: Session, window: dict) -> dict:
    rows = analytics.base_query(db, window).all()
    words = analytics.topics(db, window)["words"][:3]
    facts = {"total": len(rows), "kata_teratas": words}
    if not words:
        return {"rows": rows, "facts": facts, "evidence": [], "what": "Belum ada kata yang cukup sering muncul pada rentang ini.", "so": THIN, "now": THIN}

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
    if neg >= 40:
        so += " Kata ini berpotensi menjadi isu."
        now = f"Cari {top} di Jelajah Berita dan baca sumber di daftar bukti. Nilai perlu tidaknya penjelasan, keputusan pada pimpinan."
    else:
        now = f"Pantau kata {top} pada pembaruan berikutnya. Tidak ada tindakan yang dipaksakan."
    return {"rows": holders or rows, "facts": facts, "evidence": _top(holders), "what": what, "so": so, "now": now, "cap": True}


def _suara(db: Session, window: dict, topic: str, segment: str, area: str) -> dict:
    current = analytics.base_query(db, window).all()
    previous = analytics.base_query(db, analytics.previous_window(window)).all()
    snap = snapshot(current, previous, topic, segment, area)
    rows = [row for row in current if matches(row, topic, segment, area)]
    counts = {item["id"]: item for item in snap["komposisi"]}
    facts = {"total": snap["total"], "komposisi": snap["komposisi"], "ramai_tersedia": snap["ramai_tersedia"], "filter": {"topik": topic, "segmen": segment, "wilayah": area}}
    if not rows:
        return {"rows": rows, "facts": facts, "evidence": [], "what": "Belum ada konten eksternal untuk pilihan ini.", "so": THIN, "now": THIN}

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
        return {"rows": rows, "facts": facts, "evidence": _top(rows), "what": what, "so": so, "now": now, "cap": True}

    focus = "hoaks" if members["hoaks"] else dominant
    main_topic = Counter(topic_of(row) for row in members[dominant]).most_common(1)[0][0]
    facts.update({"suara_dominan": VOICE_LABEL[dominant], "topik_dominan": main_topic})
    so = f"Suara yang paling banyak terbaca adalah {VOICE_LABEL[dominant].lower()} ({len(members[dominant])} konten), terutama topik {main_topic}."
    if members["hoaks"]:
        so += f" Ada {len(members['hoaks'])} konten berpola hoaks yang perlu dicek sebelum menyebar."
        now = "Verifikasi konten berpola hoaks di daftar bukti, lalu bahas klarifikasi dengan pimpinan."
    elif dominant == "keluhan":
        now = f"Buka Keluhan ke Solusi untuk melihat unit terkait topik {main_topic}. Tindak lanjut diputuskan pimpinan."
    elif dominant == "kebutuhan":
        now = f"Siapkan bahan informasi atau edukasi tentang {main_topic} untuk ditinjau sebelum dipakai."
    else:
        now = "Apresiasi bisa jadi bahan komunikasi setelah disetujui pimpinan."
    return {"rows": rows, "facts": facts, "evidence": _top(members[focus]), "what": what, "so": so, "now": now, "cap": True}


def _numbers(text: str) -> set[str]:
    found = set()
    for item in re.findall(r"\d+(?:[.,]\d+)?", text):
        value = item.replace(",", ".")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        found.add(value)
    return found


def _llm(chart: str, facts: dict, base: dict) -> Optional[dict]:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return None
    payload = json.dumps({"grafik": CHARTS[chart], "data": facts}, ensure_ascii=False, default=str)
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
    parts = [str(data.get(name) or "").strip() for name in ("what_happened", "so_what", "now_what")]
    if not all(parts):
        return None
    blob = " ".join(parts)
    if re.search(r"https?://|www\.", blob):
        return None
    allowed = _numbers(payload + " " + base["what"])
    if not _numbers(blob) <= allowed:
        return None
    return {"what": parts[0], "so": parts[1], "now": parts[2]}


def _cap(level: str, no_baseline: bool) -> str:
    return "Sedang" if no_baseline and level == "Tinggi" else level


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
    sections = {"what": result["what"], "so": result["so"], "now": result["now"]}
    method = "Aturan dari data grafik"
    if not thin:
        rewritten = _llm(chart, result["facts"], result)
        if rewritten:
            sections = rewritten
            method = f"Model bahasa ({configured_model()}), angka diperiksa terhadap data"
    else:
        sections["so"] = THIN
        sections["now"] = THIN
    return {
        "chart": chart,
        "title": CHARTS[chart],
        "period": {"from": window["date_from"].isoformat(), "to": window["date_to"].isoformat()},
        "what_happened": sections["what"],
        "so_what": sections["so"],
        "now_what": sections["now"],
        "keyakinan": "Rendah" if thin else _cap(confidence_of(rows), result.get("no_baseline", False) or result.get("cap", False)),
        "insufficient": thin,
        "evidence": result["evidence"],
        "method": method,
    }
