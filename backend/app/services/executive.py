"""Top 10 isu untuk pimpinan.

Isu memakai pengelompokan yang sudah ada: mention yang punya issue_id digabung,
sisanya dikelompokkan menurut kategori dan tag kebijakan. Bukan embedding.
Ringkasan disalin dari judul dan tautan tersimpan. Model bahasa hanya
dipakai bila LLM_API_KEY ada, dan ditolak bila menambah URL atau angka.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.constants import JAKARTA_AREAS
from app.models import ExecutiveCache, Issue, Mention
from app.services.analytics import base_query, previous_window
from app.services.clock import now_wib

BI_CATEGORIES = {
    "Kebijakan Moneter",
    "Sistem Pembayaran",
    "Rupiah/Kurs",
    "Inflasi",
    "Perbankan/Kredit",
    "Pengedaran Uang",
    "Reputasi/Kelembagaan",
    "Hoaks/Penipuan",
}
PROVINCES = [
    "Kepulauan Riau", "Sumatera Utara", "Sumatera Barat", "Sumatera Selatan",
    "Kalimantan Barat", "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur", "Kalimantan Utara",
    "Sulawesi Utara", "Sulawesi Tengah", "Sulawesi Selatan", "Sulawesi Tenggara", "Sulawesi Barat",
    "Nusa Tenggara Barat", "Nusa Tenggara Timur", "Bangka Belitung", "DI Yogyakarta",
    "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Papua Barat Daya", "Papua Pegunungan",
    "Papua Selatan", "Papua Tengah", "Papua Barat", "Maluku Utara",
    "Aceh", "Riau", "Jambi", "Bengkulu", "Lampung", "Banten", "Bali", "Gorontalo", "Maluku", "Papua",
]
SCOPES = {"nasional", "dki", "lainnya"}


def provinces() -> list[str]:
    return list(PROVINCES)


def build(db: Session, window: dict, scope: str, province: str = "", refresh: bool = False) -> dict:
    if scope not in SCOPES:
        raise ValueError("Cakupan tidak dikenal")
    key = _key(scope, window, province)
    if not refresh:
        cached = db.query(ExecutiveCache).filter(ExecutiveCache.cache_key == key).one_or_none()
        if cached and cached.payload:
            data = json.loads(cached.payload)
            data["cached"] = True
            data["updated_at"] = cached.updated_at.isoformat(timespec="minutes")
            return data
    payload = _compute(db, window, scope, province)
    row = db.query(ExecutiveCache).filter(ExecutiveCache.cache_key == key).one_or_none()
    if row is None:
        row = ExecutiveCache(cache_key=key, payload="{}", updated_at=now_wib())
        db.add(row)
    row.payload = json.dumps(payload, ensure_ascii=False)
    row.updated_at = now_wib()
    db.commit()
    payload["cached"] = False
    payload["updated_at"] = row.updated_at.isoformat(timespec="minutes")
    return payload


def workbook(db: Session, window: dict) -> bytes:
    book = Workbook()
    first = True
    for scope, title in (("nasional", "Nasional"), ("dki", "KPw DKI"), ("lainnya", "KPw lain")):
        data = build(db, window, scope)
        sheet = book.active if first else book.create_sheet(title)
        first = False
        sheet.title = title
        sheet.append(["Peringkat", "Judul isu", "Sentimen", "Volume", "Perubahan %", "Provinsi", "Ringkasan", "Tautan"])
        for item in data["items"]:
            links = " | ".join(f"{link['source_name']}: {link['title']} {link['url']}" for link in item["links"])
            sheet.append([
                item["rank"], item["title"], item["stance"], item["volume"],
                item["delta_pct"] if item["delta_pct"] is not None else "",
                item.get("province") or "", item["summary"], links,
            ])
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _compute(db: Session, window: dict, scope: str, province: str) -> dict:
    current = _placed(base_query(db, window).all(), scope, province)
    previous = _placed(base_query(db, previous_window(window)).all(), scope, province)
    prev_counts = {key: len(rows) for key, rows in _groups(previous).items()}
    ranked = []
    for key, rows in _groups(current).items():
        links = _links(rows)
        if len(links) < 2:
            continue
        card = _card(db, key, rows, prev_counts.get(key, 0))
        if province and card["province"] != province:
            continue
        ranked.append(card)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    items = []
    for index, card in enumerate(ranked[:10], start=1):
        card["rank"] = index
        items.append(card)
    return {
        "scope": scope,
        "province": province,
        "period": {"from": window["date_from"].isoformat(), "to": window["date_to"].isoformat()},
        "method": "Klaster dari isu tersimpan atau kategori+tag kebijakan. Ringkasan menyalin judul dan tautan yang ada di basis data.",
        "items": items,
        "provinces": sorted({card["province"] for card in ranked if card.get("province")}),
    }


def _placed(rows: list, scope: str, province: str) -> list:
    kept = []
    for row in rows:
        row_scope, row_province = _scope(row)
        if row_scope != scope:
            continue
        if province and row_province != province:
            continue
        kept.append(row)
    return kept


def _scope(row: Mention) -> tuple[str, str]:
    hay = f"{row.location or ''} {row.title or ''} {row.text or ''}"
    folded = hay.casefold()
    if row.location in JAKARTA_AREAS or row.category in {"Kegiatan KPw DKI", "Ekonomi Jakarta"} or "dki jakarta" in folded:
        return "dki", "DKI Jakarta"
    for name in sorted(PROVINCES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(name.casefold()) + r"\b", folded):
            return "lainnya", name
    return "nasional", ""


def _groups(rows: list) -> dict[str, list]:
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        if row.issue_id:
            key = f"issue:{row.issue_id}"
        else:
            tags = json.loads(row.policy_tags or "[]")
            tag = tags[0] if tags else "Umum"
            key = f"topik:{row.category}:{tag}"
        groups[key].append(row)
    return groups


def _card(db: Session, key: str, rows: list, previous: int) -> dict:
    rows = sorted(rows, key=lambda item: item.published_at)
    issue = db.get(Issue, rows[0].issue_id) if key.startswith("issue:") else None
    title = (issue.title if issue else rows[-1].title)[:300]
    sentiments = [row.sentiment for row in rows]
    total = len(rows) or 1
    mix = {
        "positif": round(sentiments.count("positif") / total * 100, 1),
        "netral": round(sentiments.count("netral") / total * 100, 1),
        "negatif": round(sentiments.count("negatif") / total * 100, 1),
    }
    stance = _dominant(rows)
    volume = len(rows)
    delta = None if previous == 0 else round((volume - previous) / previous * 100, 1)
    if previous == 0 and volume:
        delta = 100.0
    province = ""
    scopes = [_scope(row) for row in rows]
    if any(item[0] == "lainnya" for item in scopes):
        names = [item[1] for item in scopes if item[1]]
        province = max(set(names), key=names.count) if names else ""
    elif any(item[0] == "dki" for item in scopes):
        province = "DKI Jakarta"
    tier1 = sum(1 for row in rows if (row.source_tier or 2) == 1)
    relevance = 20 if rows[-1].category in BI_CATEGORIES else 0
    score = volume * 2 + tier1 * 3 + relevance
    links = _links(rows)
    summary = _summary(title, rows, stance, mix, links)
    summary = _maybe_llm(summary, links)
    return {
        "key": key,
        "title": title,
        "stance": stance,
        "mix": mix,
        "volume": volume,
        "previous": previous,
        "delta_pct": delta,
        "province": province,
        "summary": summary,
        "links": links,
        "score": score,
        "category": rows[-1].category,
    }


def _dominant(rows: list) -> str:
    counts = {"positif": 0, "netral": 0, "negatif": 0}
    for row in rows:
        counts[row.sentiment if row.sentiment in counts else "netral"] += 1
    if counts["negatif"] > counts["positif"] and counts["negatif"] >= counts["netral"]:
        return "downside"
    if counts["positif"] > counts["negatif"] and counts["positif"] >= counts["netral"]:
        return "upside"
    return "netral"


def _links(rows: list) -> list[dict]:
    ordered = sorted(rows, key=lambda item: ((item.source_tier or 9), -(item.reach_estimate or 0)))
    seen = set()
    links = []
    for row in ordered:
        url = (row.url or "").strip()
        if not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        links.append({
            "source_name": row.source_name,
            "title": row.title,
            "url": url,
            "published_at": row.published_at.isoformat(timespec="minutes"),
        })
        if len(links) == 5:
            break
    return links


def _plain(value: str) -> str:
    return re.sub(r"[.!?]+", ",", value or "").strip(" ,")


def _summary(title: str, rows: list, stance: str, mix: dict, links: list[dict]) -> str:
    names = []
    for link in links:
        name = _plain(link["source_name"])
        if name and name not in names:
            names.append(name)
    media = ", ".join(names[:4]) or "media yang tersimpan"
    start = rows[0].published_at.strftime("%d %b %Y")
    end = rows[-1].published_at.strftime("%d %b %Y")
    label = {"upside": "Upside", "downside": "Downside", "netral": "Netral"}[stance]
    latest = _plain(links[0]["title"])
    safe_title = _plain(title)
    sentences = [
        f"Pada {start} sampai {end} tersimpan {len(rows)} pemberitaan yang dikelompokkan pada isu \"{safe_title}\".",
        f"Sumber yang menurunkan judul ini antara lain {media}.",
        f"Isu ini masuk kategori {rows[-1].category} dan menyebut institusi atau topik yang sudah ada pada judul sumber, termasuk Bank Indonesia bila nama itu tertulis di judul.",
        "Konteks yang dapat dibaca terbatas pada judul dan tautan yang tersimpan, bukan pada teks lengkap artikel.",
        f"Komposisi klasifikasi otomatis adalah {round(mix['positif'])}% positif, {round(mix['netral'])}% netral, dan {round(mix['negatif'])}% negatif, sehingga label dominan adalah {label}.",
        "Dampak terhadap kebijakan, rupiah, inflasi, sistem pembayaran, atau stabilitas tidak dihitung sebagai angka baru.",
        f"Perkembangan terkini pada klaster ini adalah judul \"{latest}\" tanggal {end}.",
        "Ringkasan ini menyalin fakta dari basis data dan tidak menambahkan peristiwa di luar tautan yang ditampilkan.",
    ]
    return " ".join(sentences[:8])


def _maybe_llm(summary: str, links: list[dict]) -> str:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return summary
    from app.services.dss_llm import _complete

    allowed = {item["url"] for item in links}
    numbers = set(re.findall(r"\d+(?:[.,]\d+)?", summary))
    system = (
        "Anda menulis satu paragraf Bahasa Indonesia formal, 5 sampai 8 kalimat, "
        "hanya dari ringkasan dan tautan yang diberikan. Jangan menambah URL, angka, atau peristiwa. "
        "Balas teks polos tanpa markdown."
    )
    user = json.dumps({"ringkasan": summary, "tautan": links}, ensure_ascii=False)
    raw = _complete(system, user, key)
    if not raw:
        return summary
    text = raw.strip()
    if any(url.startswith("http") and url not in allowed for url in re.findall(r"https://\S+", text)):
        return summary
    fresh = set(re.findall(r"\d+(?:[.,]\d+)?", text))
    if fresh - numbers:
        return summary
    count = len(re.findall(r"[.!?]", text))
    if count < 5 or count > 10:
        return summary
    return text


def _key(scope: str, window: dict, province: str) -> str:
    return f"{scope}|{window['date_from'].isoformat()}|{window['date_to'].isoformat()}|{province}"
