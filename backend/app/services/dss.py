"""Saran pendukung keputusan dari konten eksternal yang sudah tersimpan.

Fakta disalin dari judul, sumber, waktu, dan angka klasifikasi di database.
Inferensi diberi label. Kelompok dengan sumber di bawah ambang tidak diberi
rekomendasi tindakan, hanya status data belum cukup.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Advice, AdviceRevision, Alert, AppMeta, Issue, Mention
from app.services.blocklist import external_only, is_blocked, load_rules
from app.services.clock import now_wib
from app.services.dss_llm import GROUNDED_MODEL, PROMPT_VERSION, configured_model, rewrite_inference

DISCLAIMER = (
    "Saran ini dihasilkan AI dari data publik eksternal, bersifat pendukung, "
    "dan wajib diverifikasi serta diputuskan oleh manusia sebelum digunakan "
    "untuk komunikasi atau kebijakan resmi."
)
LOCKED = {"diterima", "ditolak", "ditunda", "selesai"}
URGENCY_RANK = {"segera": 0, "tinggi": 1, "sedang": 2, "rendah": 3}
KIND_LABEL = {
    "respons": "Saran respons komunikasi",
    "prioritas": "Saran prioritas penanganan",
    "kebijakan": "Masukan untuk kebijakan",
    "peluang": "Saran peluang",
    "mitigasi": "Saran mitigasi risiko",
}
UNIT_FOR_TOPIC = {
    "BI-Rate": "Kehumasan dan Kebijakan Moneter",
    "Nilai tukar": "Kehumasan dan Kebijakan Moneter",
    "Inflasi": "Kehumasan dan Kebijakan Moneter",
    "QRIS": "Kehumasan dan Sistem Pembayaran",
    "BI-FAST": "Kehumasan dan Sistem Pembayaran",
    "Sistem pembayaran": "Kehumasan dan Sistem Pembayaran",
    "Pengedaran uang": "Kehumasan dan Pengedaran Uang",
    "Rupiah digital": "Kehumasan dan Sistem Pembayaran",
    "Makroprudensial": "Kehumasan dan Kebijakan Moneter",
    "Perbankan/Kredit": "Kehumasan",
}


def load_settings(db: Session) -> dict:
    def _num(key: str, default: float) -> float:
        row = db.get(AppMeta, key)
        if row is None or row.value == "":
            return default
        try:
            return float(row.value)
        except ValueError:
            return default

    tone = db.get(AppMeta, "dss_tone")
    return {
        "min_sources": int(_num("dss_min_sources", 3)),
        "urgent_risk": _num("dss_urgent_risk", 70),
        "credibility_weight": _num("dss_credibility_weight", 1),
        "tone": tone.value if tone and tone.value else "formal netral",
    }


def save_settings(db: Session, body: dict) -> dict:
    mapping = {
        "min_sources": str(max(1, int(body.get("min_sources", 3)))),
        "urgent_risk": str(float(body.get("urgent_risk", 70))),
        "credibility_weight": str(float(body.get("credibility_weight", 1))),
        "tone": str(body.get("tone") or "formal netral")[:80],
    }
    for key, value in mapping.items():
        db.merge(AppMeta(key=f"dss_{key}", value=value))
    db.commit()
    return load_settings(db)


def refresh_advices(db: Session) -> dict:
    """Susun ulang saran setelah klasifikasi. Riwayat manusia tidak dihapus."""
    settings = load_settings(db)
    rules = load_rules(db)
    since = now_wib() - timedelta(days=14)
    mentions = [
        row
        for row in external_only(db.query(Mention).filter(Mention.published_at >= since), rules).all()
        if _usable(row, rules)
    ]
    issues = {row.id: row for row in db.query(Issue).all()}
    drafts = _drafts(mentions, issues, settings)
    seen: set[str] = set()
    created = updated = expired = 0
    now = now_wib()
    for draft in drafts:
        seen.add(draft["stable_key"])
        row = db.query(Advice).filter(Advice.stable_key == draft["stable_key"]).one_or_none()
        if row is None:
            row = Advice(stable_key=draft["stable_key"], created_at=now)
            db.add(row)
            _apply(row, draft, now)
            row.status = "data_belum_cukup" if draft["insufficient"] else "baru"
            _revise(db, row, "Saran baru disusun dari data eksternal.")
            _audit_row(db, "sistem", "saran_dibuat", row)
            created += 1
            continue
        changed = row.evidence_hash != draft["evidence_hash"]
        locked = row.status in LOCKED
        previous = row.status
        if locked:
            _apply(row, draft, row.generated_at, keep_human=True)
            if changed:
                row.change_note = "Bukti berubah setelah keputusan manusia. Status tinjauan tidak diubah."
                _revise(db, row, row.change_note)
                _notify(db, row, now)
                updated += 1
            continue
        _apply(row, draft, now if changed or previous == "kedaluwarsa" else row.generated_at)
        if draft["insufficient"]:
            row.status = "data_belum_cukup"
        elif previous == "kedaluwarsa":
            row.status = "diperbarui"
            row.change_note = "Saran aktif kembali karena ada bukti baru."
            _revise(db, row, row.change_note)
            updated += 1
        elif changed:
            row.status = "diperbarui"
            row.change_note = "Bukti atau skor berubah pada siklus pembaruan."
            _revise(db, row, row.change_note)
            _notify(db, row, now)
            updated += 1
    for row in db.query(Advice).all():
        if row.stable_key in seen or row.status in {"kedaluwarsa", "selesai", "ditolak"}:
            continue
        row.status = "kedaluwarsa"
        row.change_note = "Tidak ada lagi bukti eksternal pada jendela 14 hari."
        _revise(db, row, row.change_note)
        expired += 1
    db.merge(AppMeta(key="dss_refreshed_at", value=now.isoformat(timespec="minutes")))
    db.commit()
    return {"created": created, "updated": updated, "expired": expired, "active": len(seen), "refreshed_at": now.isoformat(timespec="minutes")}


def list_advices(db: Session, filters: dict, top: int = 0) -> dict:
    rows = db.query(Advice).order_by(Advice.generated_at.desc()).all()
    items = [_public(row) for row in rows]
    if filters.get("urgency"):
        items = [item for item in items if item["urgency"] == filters["urgency"]]
    if filters.get("kind"):
        items = [item for item in items if item["kind"] == filters["kind"]]
    if filters.get("category"):
        items = [item for item in items if item["category"] == filters["category"]]
    if filters.get("unit"):
        needle = filters["unit"].casefold()
        items = [item for item in items if needle in item["unit"].casefold()]
    if filters.get("status"):
        items = [item for item in items if item["status"] == filters["status"]]
    if filters.get("issue_id"):
        items = [item for item in items if item["issue_id"] == int(filters["issue_id"])]
    items.sort(key=lambda item: (URGENCY_RANK.get(item["urgency"], 9), 0 if not item["insufficient"] else 1, -item["source_count"]))
    if top:
        items = [item for item in items if item["status"] not in {"kedaluwarsa", "ditolak", "selesai"}][:top]
    refreshed = db.get(AppMeta, "dss_refreshed_at")
    return {
        "refreshed_at": refreshed.value if refreshed else None,
        "disclaimer": DISCLAIMER,
        "model_name": configured_model(),
        "prompt_version": PROMPT_VERSION,
        "items": items,
    }


def advice_timeline(db: Session, advice_id: int) -> list[dict]:
    rows = (
        db.query(AdviceRevision)
        .filter(AdviceRevision.advice_id == advice_id)
        .order_by(AdviceRevision.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "status": row.status,
            "urgency": row.urgency,
            "source_count": row.source_count,
            "note": row.note,
            "created_at": row.created_at.isoformat(timespec="minutes"),
        }
        for row in rows
    ]


def act(db: Session, advice_id: int, body: dict, actor: str) -> dict:
    row = db.get(Advice, advice_id)
    if row is None:
        return {}
    action = (body.get("action") or "").strip()
    mapping = {"terima": "diterima", "tolak": "ditolak", "tunda": "ditunda", "selesai": "selesai"}
    if action in mapping:
        row.status = mapping[action]
        row.analyst_note = body.get("analyst_note") or row.analyst_note
        if action == "tolak":
            row.feedback_reason = body.get("feedback_reason") or row.feedback_reason
        _audit_row(db, actor, f"saran_{action}", row, body.get("feedback_reason") or body.get("analyst_note") or "")
        _revise(db, row, f"{actor} menandai saran sebagai {row.status}.")
    elif action == "edit":
        if "draft_points" in body:
            row.draft_points = body.get("draft_points") or ""
            row.draft_edited = True
        if body.get("analyst_note") is not None:
            row.analyst_note = body.get("analyst_note") or ""
        if body.get("unit"):
            row.unit = str(body["unit"])[:160]
        _audit_row(db, actor, "saran_edit", row, row.draft_points[:500])
        _revise(db, row, f"{actor} mengedit draf pesan.")
    elif action == "umpan":
        row.useful = body.get("useful")
        row.feedback_reason = body.get("feedback_reason") or row.feedback_reason
        _audit_row(db, actor, "saran_umpan_balik", row, row.feedback_reason)
    else:
        return {}
    db.commit()
    db.refresh(row)
    return _public(row)


def ask(db: Session, question: str) -> dict:
    settings = load_settings(db)
    rules = load_rules(db)
    since = now_wib() - timedelta(days=14)
    rows = [
        row
        for row in external_only(db.query(Mention).filter(Mention.published_at >= since), rules).all()
        if _usable(row, rules) and _question_hits(row, question)
    ]
    evidence = [_evidence_item(row) for row in rows[:12]]
    facts = [_fact_line(row) for row in rows[:12]]
    base = {
        "disclaimer": DISCLAIMER,
        "model_name": configured_model(),
        "evidence": evidence,
        "facts": facts,
        "inferences": [],
    }
    if len(rows) < settings["min_sources"]:
        base.update(
            {
                "status": "data_belum_cukup",
                "answer": (
                    f"Data belum cukup, perlu verifikasi. Pertanyaan hanya menyentuh {len(rows)} konten eksternal "
                    f"pada 14 hari terakhir, di bawah ambang {settings['min_sources']} sumber. "
                    "Tidak ada rekomendasi yang dipaksakan."
                ),
            }
        )
        return base
    negative = sum(1 for row in rows if row.sentiment == "negatif" or row.stance == "downside")
    inference = (
        f"Inferensi: dari {len(rows)} konten yang memuat kata pada pertanyaan, {negative} berkategori negatif atau downside "
        "menurut klasifikasi otomatis. Ini bukan penilaian akhir."
    )
    answer = "Fakta dari sumber tersimpan:\n" + "\n".join(f"- {line}" for line in facts) + "\n\n" + inference
    from app.services.dss_llm import answer_question

    rewritten = answer_question(question, facts, evidence)
    if rewritten:
        answer = rewritten + "\n\nFakta yang menjadi dasar:\n" + "\n".join(f"- {line}" for line in facts)
        base["model_name"] = configured_model()
    base.update({"status": "jawaban", "answer": answer, "inferences": [inference]})
    return base


def simulate(db: Session, issue_id: int | None) -> dict:
    """Bandingkan opsi respons. Angka yang tampil adalah hitungan tersimpan, bukan ramalan."""
    settings = load_settings(db)
    rules = load_rules(db)
    query = db.query(Mention)
    if issue_id:
        query = query.filter(Mention.issue_id == issue_id)
    else:
        query = query.filter(Mention.published_at >= now_wib() - timedelta(days=14))
    rows = [row for row in external_only(query, rules).all() if _usable(row, rules)]
    evidence = [_evidence_item(row) for row in sorted(rows, key=lambda item: item.published_at, reverse=True)[:8]]
    total = len(rows)
    if total < settings["min_sources"]:
        return {
            "status": "data_belum_cukup",
            "disclaimer": DISCLAIMER,
            "answer": "Data belum cukup, perlu verifikasi. Simulasi tidak dijalankan agar tidak mengarang dampak.",
            "measured": {},
            "options": [],
            "evidence": evidence,
        }
    negative = sum(1 for row in rows if row.sentiment == "negatif" or row.stance == "downside")
    positive = sum(1 for row in rows if row.sentiment == "positif" or row.stance == "upside")
    measured = {
        "total": total,
        "negatif": negative,
        "positif": positive,
        "netral": total - negative - positive,
        "catatan": "Komposisi ini dihitung dari klasifikasi yang tersimpan. Jangkauan platform tidak tersedia. Perkiraan di bawah adalah arah, bukan perubahan angka.",
    }
    options = [
        _option("Tidak merespons", "Komposisi sentimen yang terukur tetap menjadi bahan yang beredar, tanpa penjelasan resmi di luar data ini.", "Tidak menambah pernyataan yang belum dicek. Versi yang sudah tayang tidak diluruskan."),
        _option("Klarifikasi media sosial", "Arah estimasi: menambah satu penjelasan singkat. Perubahan persen sentimen tidak bisa dihitung dari data yang ada.", "Lebih cepat dari siaran pers, tetapi jangkauannya tidak terukur di feed ini."),
        _option("Siaran pers", "Arah estimasi: memberi rujukan tertulis bagi media yang sudah memberitakan. Dampak angka tidak tersedia.", "Lebih formal, tetapi lebih lambat dan tidak otomatis memperbaiki nada judul yang sudah tayang."),
        _option("Edukasi atau FAQ", "Arah estimasi: berguna bila judul yang tersimpan bersifat penjelasan, bukan sanggahan. Dampak angka tidak tersedia.", "Lebih aman bila fakta belum lengkap, tetapi tidak menjawab kritik yang sudah spesifik."),
    ]
    return {
        "status": "estimasi",
        "disclaimer": "Ini estimasi kualitatif, bukan prediksi sentimen. Tidak ada tindakan yang dikirim ke luar.",
        "measured": measured,
        "options": options,
        "evidence": evidence,
    }


def briefing_rows(db: Session) -> list[Advice]:
    return [
        row
        for row in db.query(Advice).all()
        if row.status not in {"kedaluwarsa", "ditolak"} and json.loads(row.evidence or "[]")
    ]


def _drafts(mentions: list[Mention], issues: dict[int, Issue], settings: dict) -> list[dict]:
    grouped: dict[int, list[Mention]] = defaultdict(list)
    for row in mentions:
        if row.issue_id in issues:
            grouped[row.issue_id].append(row)
    drafts: list[dict] = []
    for issue_id, rows in grouped.items():
        issue = issues[issue_id]
        drafts.append(_communication(issue, rows, settings))
        if _upside(rows):
            drafts.append(_opportunity(issue, rows, settings))
    risky = [row for row in mentions if row.needs_verification or "hoaks" in f"{row.title} {row.text}".casefold() or "penipuan" in f"{row.title} {row.text}".casefold() or row.category == "Hoaks/Penipuan"]
    if risky:
        drafts.append(_mitigation(risky, settings))
    if grouped:
        drafts.append(_priority(grouped, issues, settings))
    by_topic: dict[str, list[Mention]] = defaultdict(list)
    for row in mentions:
        for tag in json.loads(row.policy_tags or "[]"):
            by_topic[tag].append(row)
    for topic, rows in by_topic.items():
        drafts.append(_policy(topic, rows, settings))
    return [draft for draft in drafts if draft.get("evidence")]


def _communication(issue: Issue, rows: list[Mention], settings: dict) -> dict:
    pack = _pack(rows)
    thin = pack["count"] < settings["min_sources"]
    verify = any(row.needs_verification for row in rows)
    channel, action = _channel(rows, verify, thin)
    urgency = "rendah" if thin else _urgency(rows, settings, verify)
    confidence = "rendah" if thin or pack["diversity"] < 2 else ("tinggi" if pack["diversity"] >= 3 and pack["tier1"] else "sedang")
    facts = _count_facts(pack, rows)
    inferences = [] if thin else [
        f"Inferensi: kanal yang lebih sesuai saat ini adalah {channel}, mengingat {pack['tier1']} sumber arus utama dan {pack['downside']} konten downside.",
        "Inferensi dampak angka pada sentimen tidak tersedia dari feed.",
    ]
    voice = _voice(rows)
    recommendation = "Data belum cukup, perlu verifikasi." if thin else action
    draft = "" if thin else _draft(rows, settings["tone"])
    alternatives = [
        {"option": "Kumpulkan sumber tambahan sebelum menyusun pesan", "tradeoff": "Tidak ada pernyataan sementara. Percakapan yang sudah tayang tetap tanpa tanggapan resmi."}
    ] if thin else [
        {"option": "Pantau tanpa pernyataan", "tradeoff": "Menghindari koreksi yang belum dicek, tetapi judul yang sudah beredar tidak diluruskan."},
        {"option": channel, "tradeoff": "Memberi satu rujukan resmi. Jangkauan balasan tidak terukur di data ini."},
    ]
    return _card(
        key=f"respons:{issue.id}",
        kind="respons",
        title=issue.title[:300],
        situation=_situation(issue.title, pack, rows),
        who=pack["who"],
        recommendation=recommendation,
        channel="" if thin else channel,
        urgency=urgency,
        reason=_reason(pack, thin),
        impact_follow="Tidak diperkirakan. Data belum cukup." if thin else "Inferensi: ada satu penjelasan resmi yang dapat dirujuk analis. Perubahan skor sentimen tidak diukur.",
        impact_ignore="Tidak diperkirakan. Data belum cukup." if thin else f"Inferensi: {pack['downside']} konten downside dan {pack['count']} judul yang tersimpan tetap tanpa catatan kehumasan.",
        alternatives=alternatives,
        confidence=confidence,
        pack=pack,
        rows=rows,
        facts=facts,
        inferences=inferences,
        voice=voice,
        unit="Kehumasan",
        draft=draft,
        verify=verify,
        insufficient=thin,
        issue_id=issue.id,
        category=issue.category,
        topic="",
        tone=settings["tone"],
    )


def _opportunity(issue: Issue, rows: list[Mention], settings: dict) -> dict:
    picked = [row for row in rows if row.stance == "upside" or row.sentiment == "positif"] or rows
    pack = _pack(picked)
    thin = pack["count"] < settings["min_sources"]
    outlets = sorted({row.source_name for row in picked})
    return _card(
        key=f"peluang:{issue.id}",
        kind="peluang",
        title=f"Peluang amplifikasi: {issue.title[:220]}",
        situation=_situation(issue.title, pack, picked),
        who=pack["who"],
        recommendation="Data belum cukup, perlu verifikasi." if thin else "Pertimbangkan edukasi atau amplifikasi judul positif yang sudah tayang di media eksternal. Jangan mengarang kutipan baru.",
        channel="" if thin else "Edukasi",
        urgency="rendah",
        reason=_reason(pack, thin),
        impact_follow="Tidak diperkirakan. Data belum cukup." if thin else "Inferensi: judul positif yang sudah ada dapat dijadikan bahan edukasi. Kenaikan sentimen tidak diukur.",
        impact_ignore="Tidak diperkirakan. Data belum cukup." if thin else "Inferensi: peluang edukasi pada judul yang sudah tayang tidak dipakai.",
        alternatives=[
            {"option": "Tidak mengamplifikasi", "tradeoff": "Tidak menambah beban klarifikasi, tetapi judul positif tidak dilanjutkan menjadi materi edukasi."},
            {"option": "Ajak media yang sudah memberitakan, bukan tokoh yang tidak ada di data", "tradeoff": "Kolaborasi terbatas pada sumber yang tercantum di bukti."},
        ],
        confidence="rendah" if thin else "sedang",
        pack=pack,
        rows=picked,
        facts=_count_facts(pack, picked) + [f"Media eksternal pada bukti: {', '.join(outlets[:8])}."],
        inferences=[] if thin else ["Inferensi: tokoh publik tidak ditambahkan bila tidak tercatat pada mention."],
        voice=_voice(picked),
        unit="Kehumasan",
        draft="" if thin else _draft(picked, settings["tone"]),
        verify=False,
        insufficient=thin,
        issue_id=issue.id,
        category=issue.category,
        topic="",
        tone=settings["tone"],
    )


def _mitigation(rows: list[Mention], settings: dict) -> dict:
    pack = _pack(rows)
    thin = pack["count"] < settings["min_sources"]
    return _card(
        key="mitigasi:hoaks",
        kind="mitigasi",
        title="Mitigasi konten yang perlu verifikasi atau menyebut hoaks/penipuan",
        situation=_situation("konten berpenanda verifikasi", pack, rows),
        who=pack["who"],
        recommendation="Data belum cukup, perlu verifikasi." if thin else "Verifikasi fakta internal lebih dulu. Jangan merespons publik sebelum penanda hoaks atau penipuan dicek.",
        channel="" if thin else "Klarifikasi setelah verifikasi",
        urgency="rendah" if thin else "tinggi",
        reason=_reason(pack, thin),
        impact_follow="Tidak diperkirakan. Data belum cukup." if thin else "Inferensi: verifikasi lebih dulu mengurangi risiko mengonfirmasi kabar yang belum dicek.",
        impact_ignore="Tidak diperkirakan. Data belum cukup." if thin else "Inferensi: konten berpenanda verifikasi tetap beredar tanpa catatan pengecekan.",
        alternatives=[
            {"option": "Eskalasi ke alert internal bila sumber arus utama bertambah", "tradeoff": "Tidak mempublikasikan sanggahan. Hanya menaikkan prioritas tinjauan bila tier-1 masuk pada siklus berikut."},
            {"option": "Klarifikasi singkat setelah cek fakta", "tradeoff": "Lebih cepat menenangkan, tetapi keliru bila fakta internal belum siap."},
        ],
        confidence="rendah" if thin else "sedang",
        pack=pack,
        rows=rows,
        facts=_count_facts(pack, rows),
        inferences=[] if thin else ["Inferensi skenario: bila jumlah konten berpenanda ini naik dan media tier-1 masuk, urgensi tinjauan naik pada siklus berikutnya. Angka kenaikan tidak diramalkan."],
        voice=_voice(rows),
        unit="Kehumasan",
        draft="",
        verify=True,
        insufficient=thin,
        issue_id=rows[0].issue_id,
        category="Hoaks/Penipuan",
        topic="",
        tone=settings["tone"],
    )


def _priority(grouped: dict[int, list[Mention]], issues: dict[int, Issue], settings: dict) -> dict:
    weight = settings["credibility_weight"]
    ranked = []
    evidence_rows = []
    for issue_id, rows in grouped.items():
        pack = _pack(rows)
        score = max(row.risk_score for row in rows) + pack["tier1"] * 5 * weight + (pack["credibility"] / 100) * 10 * weight
        ranked.append((score, issues[issue_id], rows, pack))
        evidence_rows.append(max(rows, key=lambda row: row.risk_score))
    ranked.sort(key=lambda item: item[0], reverse=True)
    lines = []
    for index, (score, issue, rows, pack) in enumerate(ranked, start=1):
        lines.append(
            f"{index}. {issue.title} — risiko tersimpan {max(row.risk_score for row in rows):.1f}, "
            f"{pack['count']} sumber, {pack['downside']} downside, kecepatan sebar {max(row.spread_velocity for row in rows):.1f}, "
            f"kredibilitas tertinggi {pack['credibility']}. Skor urutan internal {score:.1f} memakai bobot kredibilitas {weight}."
        )
    pack = _pack(evidence_rows)
    thin = sum(len(rows) for _, _, rows, _ in ranked) < settings["min_sources"]
    return _card(
        key="prioritas:jendela",
        kind="prioritas",
        title="Urutan isu untuk ditinjau lebih dulu",
        situation="Urutan berikut memakai risk score, jumlah sumber, nada downside, kecepatan sebar, dan kredibilitas yang sudah tersimpan. Bukan penilaian baru.",
        who=pack["who"],
        recommendation="Data belum cukup, perlu verifikasi." if thin else "Tinjau isu dari urutan di atas. Urutan adalah alat bantu, bukan penugasan otomatis.",
        channel="",
        urgency="rendah" if thin else _urgency(evidence_rows, settings, False),
        reason="\n".join(lines),
        impact_follow="Inferensi: isu dengan risiko dan jumlah sumber lebih tinggi ditinjau lebih dulu." if not thin else "Tidak diperkirakan. Data belum cukup.",
        impact_ignore="Inferensi: isu dengan downside tetap tanpa urutan tinjauan." if not thin else "Tidak diperkirakan. Data belum cukup.",
        alternatives=[{"option": "Urutkan manual oleh analis", "tradeoff": "Mengabaikan bobot otomatis, tetapi tetap harus memakai bukti yang sama."}],
        confidence="rendah" if thin else "sedang",
        pack=pack,
        rows=evidence_rows,
        facts=lines,
        inferences=["Inferensi: skor urutan hanya untuk mengurutkan, bukan ukuran dampak publik yang baru."],
        voice="",
        unit="Kehumasan",
        draft="",
        verify=any(row.needs_verification for row in evidence_rows),
        insufficient=thin,
        issue_id=ranked[0][1].id if ranked else None,
        category="",
        topic="",
        tone=settings["tone"],
    )


def _policy(topic: str, rows: list[Mention], settings: dict) -> dict:
    pack = _pack(rows)
    thin = pack["count"] < settings["min_sources"]
    upside = [row.title for row in rows if row.stance == "upside"][:3]
    downside = [row.title for row in rows if row.stance == "downside"][:3]
    facts = _count_facts(pack, rows)
    if upside:
        facts.append("Judul bernada upside: " + " | ".join(upside))
    if downside:
        facts.append("Judul bernada downside: " + " | ".join(downside))
    facts.append("Ini rangkuman persepsi pada judul yang tersimpan, bukan rekomendasi kebijakan moneter.")
    return _card(
        key=f"kebijakan:{topic.casefold()}",
        kind="kebijakan",
        title=f"Persepsi publik tentang {topic}",
        situation=_situation(topic, pack, rows),
        who=pack["who"],
        recommendation="Data belum cukup, perlu verifikasi." if thin else f"Unit kebijakan dapat membaca judul eksternal tentang {topic} sebagai masukan persepsi. Bukan usulan mengubah kebijakan.",
        channel="",
        urgency="rendah",
        reason=_reason(pack, thin),
        impact_follow="Inferensi: rapat punya daftar judul dan tautan yang bisa dibuka." if not thin else "Tidak diperkirakan. Data belum cukup.",
        impact_ignore="Inferensi: persepsi pada judul ini tidak masuk bahan rapat." if not thin else "Tidak diperkirakan. Data belum cukup.",
        alternatives=[{"option": "Tunda sampai jumlah sumber mencapai ambang", "tradeoff": "Bahan rapat lebih tipis, tetapi tidak menyamar sedikit judul sebagai gambaran publik."}],
        confidence="rendah" if thin else "sedang",
        pack=pack,
        rows=rows[:8],
        facts=facts,
        inferences=["Inferensi: kritik atau aspirasi dibaca dari stance tersimpan, bukan dari survei baru."],
        voice=_voice(rows),
        unit=UNIT_FOR_TOPIC.get(topic, "Kehumasan"),
        draft="",
        verify=any(row.needs_verification for row in rows),
        insufficient=thin,
        issue_id=None,
        category=topic,
        topic=topic,
        tone=settings["tone"],
    )


def _card(**kwargs) -> dict:
    rows = kwargs["rows"]
    evidence = [_evidence_item(row) for row in rows if row.url.startswith("http")]
    if not evidence:
        return {"evidence": []}
    pack = kwargs["pack"]
    digest = hashlib.sha256(",".join(str(item["mention_id"]) for item in evidence).encode()).hexdigest()
    model = GROUNDED_MODEL
    draft = {
        "stable_key": kwargs["key"],
        "kind": kwargs["kind"],
        "title": kwargs["title"][:300],
        "situation": kwargs["situation"],
        "who": kwargs["who"],
        "recommendation": kwargs["recommendation"],
        "channel": kwargs["channel"],
        "urgency": kwargs["urgency"],
        "reason": kwargs["reason"],
        "impact_follow": kwargs["impact_follow"],
        "impact_ignore": kwargs["impact_ignore"],
        "alternatives": kwargs["alternatives"],
        "confidence": kwargs["confidence"],
        "source_count": pack["count"],
        "source_diversity": pack["diversity"],
        "evidence": evidence,
        "facts": kwargs["facts"],
        "inferences": kwargs["inferences"],
        "public_voice": kwargs["voice"],
        "unit": kwargs["unit"],
        "draft_points": kwargs["draft"],
        "needs_verification": kwargs["verify"],
        "insufficient": kwargs["insufficient"],
        "issue_id": kwargs["issue_id"],
        "category": kwargs["category"],
        "policy_topic": kwargs["topic"],
        "model_name": model,
        "prompt_version": PROMPT_VERSION,
        "evidence_hash": digest,
        "tone": kwargs["tone"],
    }
    if not draft["insufficient"]:
        rewritten = rewrite_inference(draft)
        if rewritten:
            draft["recommendation"] = str(rewritten.get("recommendation") or draft["recommendation"])[:2000]
            draft["draft_points"] = str(rewritten.get("draft_points") or draft["draft_points"])[:2000]
            draft["reason"] = str(rewritten.get("reason") or draft["reason"])[:2000]
            draft["impact_follow"] = str(rewritten.get("impact_follow") or draft["impact_follow"])[:1000]
            draft["impact_ignore"] = str(rewritten.get("impact_ignore") or draft["impact_ignore"])[:1000]
            alts = rewritten.get("alternatives") or []
            if isinstance(alts, list) and alts:
                draft["alternatives"] = [
                    {"option": str(item.get("option") or "")[:300], "tradeoff": str(item.get("tradeoff") or "")[:400]}
                    for item in alts
                    if isinstance(item, dict) and item.get("option")
                ] or draft["alternatives"]
            extra = rewritten.get("inferences")
            if isinstance(extra, list):
                draft["inferences"] = [str(item)[:400] for item in extra[:4]] or draft["inferences"]
            draft["model_name"] = configured_model()
    if len(draft["alternatives"]) < 1:
        draft["alternatives"] = [{"option": "Tinjau bukti secara manual", "tradeoff": "Lebih lambat, tetapi tidak bergantung pada urutan otomatis."}]
    return draft


def _apply(row: Advice, draft: dict, generated_at, keep_human: bool = False) -> None:
    row.kind = draft["kind"]
    row.title = draft["title"]
    row.situation = draft["situation"]
    row.who = draft["who"]
    row.recommendation = draft["recommendation"]
    row.channel = draft["channel"]
    row.urgency = draft["urgency"]
    row.reason = draft["reason"]
    row.impact_follow = draft["impact_follow"]
    row.impact_ignore = draft["impact_ignore"]
    row.alternatives = json.dumps(draft["alternatives"], ensure_ascii=False)
    row.confidence = draft["confidence"]
    row.source_count = draft["source_count"]
    row.source_diversity = draft["source_diversity"]
    row.evidence = json.dumps(draft["evidence"], ensure_ascii=False)
    row.facts = json.dumps(draft["facts"], ensure_ascii=False)
    row.inferences = json.dumps(draft["inferences"], ensure_ascii=False)
    row.public_voice = draft["public_voice"]
    row.needs_verification = draft["needs_verification"]
    row.insufficient = draft["insufficient"]
    row.issue_id = draft["issue_id"]
    row.category = draft["category"]
    row.policy_topic = draft["policy_topic"]
    row.model_name = draft["model_name"]
    row.prompt_version = draft["prompt_version"]
    row.evidence_hash = draft["evidence_hash"]
    row.generated_at = generated_at
    if keep_human:
        return
    if not row.draft_edited:
        row.draft_points = draft["draft_points"]
    row.unit = draft["unit"]
    if not row.status:
        row.status = "data_belum_cukup" if draft["insufficient"] else "baru"


def _public(row: Advice) -> dict:
    evidence = [item for item in json.loads(row.evidence or "[]") if str(item.get("url") or "").startswith("http")]
    return {
        "id": row.id,
        "kind": row.kind,
        "kind_label": KIND_LABEL.get(row.kind, row.kind),
        "title": row.title,
        "situation": row.situation,
        "who": row.who,
        "recommendation": row.recommendation,
        "channel": row.channel,
        "urgency": row.urgency,
        "reason": row.reason,
        "impact_follow": row.impact_follow,
        "impact_ignore": row.impact_ignore,
        "alternatives": json.loads(row.alternatives or "[]"),
        "confidence": row.confidence,
        "source_count": row.source_count,
        "source_diversity": row.source_diversity,
        "evidence": evidence,
        "facts": json.loads(row.facts or "[]"),
        "inferences": json.loads(row.inferences or "[]"),
        "public_voice": row.public_voice,
        "unit": row.unit,
        "draft_points": row.draft_points,
        "needs_verification": row.needs_verification,
        "insufficient": row.insufficient,
        "status": row.status,
        "analyst_note": row.analyst_note,
        "useful": row.useful,
        "feedback_reason": row.feedback_reason,
        "issue_id": row.issue_id,
        "category": row.category,
        "policy_topic": row.policy_topic,
        "model_name": row.model_name,
        "prompt_version": row.prompt_version,
        "change_note": row.change_note,
        "generated_at": row.generated_at.isoformat(timespec="minutes") if row.generated_at else None,
        "disclaimer": DISCLAIMER,
    }


def _revise(db: Session, row: Advice, note: str) -> None:
    if row.id is None:
        db.flush()
    db.add(
        AdviceRevision(
            advice_id=row.id,
            status=row.status or "baru",
            urgency=row.urgency or "",
            source_count=row.source_count or 0,
            note=note[:500],
            created_at=now_wib(),
        )
    )


def _notify(db: Session, row: Advice, now) -> None:
    title = f"Saran diperbarui: {row.title[:180]}"
    start = now - timedelta(hours=12)
    exists = db.query(Alert).filter(Alert.title == title, Alert.triggered_at >= start).first()
    if exists:
        return
    db.add(Alert(rule_id=None, title=title, message=row.change_note or "Bukti saran berubah.", severity="waspada", triggered_at=now, is_read=False, issue_id=row.issue_id))


def _audit_row(db: Session, actor: str, action: str, row: Advice, note: str = "") -> None:
    from app.models import AuditLog

    db.add(
        AuditLog(
            actor=actor,
            action=action,
            entity_type="advice",
            entity_id=str(row.id or row.stable_key),
            old_value=row.model_name or "",
            new_value=f"{row.prompt_version} {row.status} {note}"[:2000],
            created_at=now_wib(),
        )
    )


def _usable(row: Mention, rules) -> bool:
    if not row.url or not str(row.url).startswith("http"):
        return False
    if "news.google.com" in row.url or "contoh.media-monitor.local" in row.url:
        return False
    return not is_blocked(row.url, row.author_handle, row.author_name, row.source_name, row.title, rules)


def _pack(rows: list[Mention]) -> dict:
    sources = sorted({row.source_name for row in rows if row.source_name})
    return {
        "count": len(rows),
        "diversity": len(sources),
        "who": ", ".join(sources[:12]),
        "tier1": sum(1 for row in rows if row.source_tier == 1),
        "downside": sum(1 for row in rows if row.stance == "downside" or row.sentiment == "negatif"),
        "upside": sum(1 for row in rows if row.stance == "upside" or row.sentiment == "positif"),
        "credibility": max((row.credibility or 0) for row in rows) if rows else 0,
        "risk": max((row.risk_score or 0) for row in rows) if rows else 0,
        "velocity": max((row.spread_velocity or 0) for row in rows) if rows else 0,
        "since": min(row.published_at for row in rows).strftime("%d %b %Y %H.%M WIB") if rows else "",
    }


def _situation(subject: str, pack: dict, rows: list[Mention]) -> str:
    return (
        f"Sejak {pack['since']} tersimpan {pack['count']} konten eksternal tentang {subject}. "
        f"Yang membicarakan: {pack['who'] or 'sumber tanpa nama'}. "
        "Kalimat ini menyalin jumlah, waktu, dan nama sumber dari database, bukan dari ringkasan baru."
    )


def _reason(pack: dict, thin: bool) -> str:
    if thin:
        return (
            f"Hanya {pack['count']} sumber ({pack['diversity']} nama media/akun). "
            "Di bawah ambang, jadi tidak ada rekomendasi tindakan yang dipaksakan."
        )
    return (
        f"Dasar urutan dan urgensi dari data tersimpan: {pack['count']} sumber, {pack['diversity']} nama berbeda, "
        f"{pack['downside']} downside, {pack['tier1']} media tier-1, risiko tertinggi {pack['risk']:.1f}, "
        f"kecepatan sebar {pack['velocity']:.1f}, kredibilitas tertinggi {pack['credibility']}. "
        "Jangkauan tidak tersedia dari feed, bukan nol pembaca."
    )


def _count_facts(pack: dict, rows: list[Mention]) -> list[str]:
    return [
        f"Jumlah konten: {pack['count']}. Nama sumber berbeda: {pack['diversity']}.",
        f"Sejak {pack['since']}.",
        f"Downside atau negatif: {pack['downside']}. Upside atau positif: {pack['upside']}.",
        "Judul yang menjadi bukti: " + " | ".join(row.title[:140] for row in rows[:6]),
    ]


def _voice(rows: list[Mention]) -> str:
    negative = [row for row in rows if row.stance == "downside" or row.sentiment == "negatif"]
    if not negative:
        return "Opini atau emosi publik yang tegas tidak tertandai pada klasifikasi judul ini. Nada mayoritas bukan downside."
    titles = "; ".join(row.title[:120] for row in negative[:3])
    return f"Opini/emosi publik menurut klasifikasi otomatis, bukan penilaian manusia: judul downside atau negatif — {titles}."


def _draft(rows: list[Mention], tone: str) -> str:
    lines = [f"Nada draf: {tone}. Poin di bawah menyalin judul sumber, bukan kutipan artikel penuh."]
    for row in rows[:4]:
        lines.append(f"- {row.source_name}: {row.title}")
    lines.append("- Analis dapat mengedit poin ini sebelum dipakai. Sistem tidak mengirimkannya.")
    return "\n".join(lines)


def _channel(rows: list[Mention], verify: bool, thin: bool) -> tuple[str, str]:
    if thin:
        return "", "Data belum cukup, perlu verifikasi."
    if verify:
        return "Klarifikasi setelah verifikasi", "Verifikasi lebih dulu. Jangan mengeluarkan pernyataan sebelum penanda hoaks atau penipuan dicek."
    tier1 = sum(1 for row in rows if row.source_tier == 1)
    downside = sum(1 for row in rows if row.stance == "downside" or row.sentiment == "negatif")
    if tier1 and downside:
        return "Siaran pers atau penjelasan ke media yang sudah memberitakan", "Siapkan penjelasan untuk media arus utama yang sudah menurunkan judul downside. Jangan mempublikasikan sebelum analis menyetujui."
    if downside:
        return "Klarifikasi media sosial", "Siapkan klarifikasi singkat. Publikasi tetap keputusan manusia."
    if any(row.stance == "upside" for row in rows):
        return "Edukasi", "Judul yang tersimpan lebih condong positif. Bahan dapat dipakai untuk edukasi, bukan sanggahan."
    return "FAQ", "Tidak ada downside yang dominan. Cukup siapkan jawaban singkat bila pertanyaan yang sama muncul."


def _urgency(rows: list[Mention], settings: dict, verify: bool) -> str:
    risk = max(row.risk_score or 0 for row in rows)
    downside = sum(1 for row in rows if row.stance == "downside" or row.sentiment == "negatif")
    tier1 = sum(1 for row in rows if row.source_tier == 1)
    if risk >= settings["urgent_risk"] or (verify and len(rows) >= settings["min_sources"]):
        return "segera"
    if risk >= 50 or (downside >= 2 and tier1):
        return "tinggi"
    if risk >= 30 or downside:
        return "sedang"
    return "rendah"


def _upside(rows: list[Mention]) -> bool:
    return any(row.stance == "upside" or row.sentiment == "positif" for row in rows)


def _evidence_item(row: Mention) -> dict:
    return {
        "mention_id": row.id,
        "title": row.title,
        "source_name": row.source_name,
        "published_at": row.published_at.isoformat(timespec="minutes"),
        "url": row.url,
        "platform": row.platform,
        "sentiment": row.sentiment,
        "risk_score": row.risk_score,
        "needs_verification": bool(row.needs_verification),
        "quotes_bi": bool(row.quotes_bi),
    }


def _fact_line(row: Mention) -> str:
    return f"{row.source_name} ({row.published_at.strftime('%d %b %Y %H.%M')} WIB): {row.title} — {row.url}"


def _question_hits(row: Mention, question: str) -> bool:
    stop = {
        "yang", "untuk", "dengan", "dari", "pada", "minggu", "publik", "kritik", "ringkas",
        "soal", "tentang", "atau", "adalah", "ini", "itu", "apa", "bagaimana", "respons",
        "terbaik", "saran", "hari", "sudah", "ada", "kalau", "jika", "bisa", "tidak",
    }
    tokens = [part for part in question.casefold().replace("?", " ").split() if len(part) >= 4 and part not in stop]
    if not tokens:
        return False
    hay = f"{row.title}\n{row.text}\n{row.policy_tags}".casefold()
    return any(token in hay for token in tokens)


def _option(name: str, estimate: str, tradeoff: str) -> dict:
    return {"option": name, "estimate": estimate, "tradeoff": tradeoff, "label": "Estimasi, bukan prediksi"}
