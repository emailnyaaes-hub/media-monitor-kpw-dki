"""Early Warning System (EWS) untuk pantauan media KPw BI DKI.

Aturan membaca mention tersimpan, memicu alert berlapis (info → waspada → kritis),
dan menyertakan playbook tindakan yang masuk kewenangan komunikasi/koordinasi.
Pengiriman email/WhatsApp belum diaktifkan; kanal tetap dicatat di aturan.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Alert, AlertRule, Mention
from app.nlp.voice import complaint_count, fastest_narrative, hoax_hits, voices_of
from app.services.clock import now_wib

SOCIAL_PLATFORMS = {"x", "instagram", "facebook", "threads", "tiktok", "youtube"}

RULE_META = {
    "negative_growth": {
        "label": "Lonjakan mention negatif",
        "why": "Nada negatif naik dibanding jendela sebelumnya — sinyal tekanan reputasi.",
    },
    "keyword_count": {
        "label": "Kata sensitif berulang",
        "why": "Kata pantauan muncul sering; perlu cek apakah isu tunggal atau noise.",
    },
    "tier1_downside": {
        "label": "Media arus utama downside",
        "why": "Media tier-1 mengangkat nada downside — jangkauan dan kredibilitas tinggi.",
    },
    "kpw_negative": {
        "label": "Tekanan narasi KPw",
        "why": "Mention negatif terkait KPw/DKI naik — relevan langsung untuk kantor perwakilan.",
    },
    "volume_spike": {
        "label": "Volume mention ramai",
        "why": "Lalu lintas percakapan di atas ambang — bisa jadi isu yang sedang memanas.",
    },
    "hoax_spread": {
        "label": "Pola bahasa hoaks",
        "why": "Deteksi pola kata hoaks/penipuan mengatasnamakan BI — bukan vonis hoaks.",
    },
    "narrative_growth": {
        "label": "Narasi tumbuh cepat",
        "why": "Satu kerangka cerita berkembang lebih cepat dari jendela sebelumnya.",
    },
    "complaint_growth": {
        "label": "Keluhan publik naik",
        "why": "Konten berkeluhan bertambah — biasanya butuh respons layanan atau edukasi.",
    },
    "high_risk": {
        "label": "Tumpukan skor risiko tinggi",
        "why": "Beberapa konten punya skor risiko di atas ambang — prioritas tinjauan analis.",
    },
    "social_amplify": {
        "label": "Amplifikasi sosial negatif",
        "why": "X/IG/FB/Threads/TikTok mengamplifikasi nada negatif di luar berita arus utama.",
    },
    "currency_stress": {
        "label": "Tekanan narasi rupiah/kurs",
        "why": "Bahasa anjlok/melemah/panik rupiah muncul — sensitif bagi mandat stabilitas.",
    },
    "quote_pressure": {
        "label": "Kutipan BI bernada negatif",
        "why": "Konten mengutip BI tetapi bernada negatif/downside — risiko salah tafsir pernyataan.",
    },
    "unverified_burst": {
        "label": "Konten belum terverifikasi",
        "why": "Banyak item bertanda perlu diverifikasi — jangan dieskalasi ke publik dulu.",
    },
    "cross_channel": {
        "label": "Isu menyeberang berita ↔ sosial",
        "why": "Isu yang sama muncul di berita dan sosial — pola eskalasi lintas kanal.",
    },
}

PLAYBOOK = {
    "negative_growth": ("Susun ringkas situasi 5W1H untuk pimpinan; bandingkan dengan jendela sebelumnya.", "Analis media"),
    "keyword_count": ("Cek konteks kata pada tautan sumber; bedakan isu tunggal vs noise kata.", "Analis media"),
    "tier1_downside": ("Baca artikel tier-1 penuh; siapkan poin klarifikasi faktual bila perlu, tanpa spekulasi.", "Kehumasan"),
    "kpw_negative": ("Petakan apakah isu lokal DKI atau nasional; libatkan unit terkait KPw bila operasional.", "Kehumasan KPw DKI"),
    "volume_spike": ("Cari isu tunggal di baliknya lewat Jelajah; jangan anggap volume = krisis.", "Analis media"),
    "hoax_spread": ("Klarifikasi hanya setelah cek tautan. Sertakan cara kenali kanal resmi BI.", "Kehumasan"),
    "narrative_growth": ("Petakan narasi yang tumbuh; siapkan materi edukasi/penjelasan sesuai fakta tertulis.", "Kehumasan"),
    "complaint_growth": ("Koordinasikan dengan unit layanan terkait (mis. sistem pembayaran) sebelum komunikasi publik.", "Koordinasi unit"),
    "high_risk": ("Tinjau item berisiko tinggi dalam 1 jam kerja; siapkan opsi eskalasi internal.", "Analis media"),
    "social_amplify": ("Pantau thread/unggahan sosial; bedakan opini viral vs fakta media arus utama.", "Analis media"),
    "currency_stress": ("Jangan spekulasi arah kurs. Siapkan materi edukasi faktual bila narasi menyesatkan.", "Kehumasan"),
    "quote_pressure": ("Cocokkan kutipan dengan siaran/pernyataan resmi; koreksi bila ada distorsi.", "Kehumasan"),
    "unverified_burst": ("Tahan komunikasi publik; lengkapi verifikasi tautan dan sumber dulu.", "Analis media"),
    "cross_channel": ("Anggap sinyal eskalasi: pantau berita + sosial bersama, siapkan briefing singkat.", "Analis + Kehumasan"),
}

CURRENCY_TERMS = (
    "rupiah anjlok",
    "rupiah melemah",
    "rupiah jatuh",
    "rupiah ambruk",
    "kurs dollar",
    "kurs dolar",
    "dolar as",
    "panik rupiah",
    "krisis rupiah",
    "nilai tukar",
)


def ensure_ews_rules(db: Session) -> None:
    names = {row.name for row in db.query(AlertRule).all()}
    specs = (
        ("Pola bahasa hoaks mulai terbaca", "hoax_spread", 2, 24, "kritis"),
        ("Skor risiko tinggi menumpuk", "high_risk", 70, 24, "kritis"),
        ("Media arus utama mengangkat downside", "tier1_downside", 2, 24, "waspada"),
        ("Sosial media mengamplifikasi nada negatif", "social_amplify", 3, 24, "waspada"),
        ("Tekanan narasi rupiah/kurs", "currency_stress", 2, 24, "waspada"),
        ("Kutipan BI bernada negatif", "quote_pressure", 2, 48, "waspada"),
        ("Narasi baru tumbuh cepat", "narrative_growth", 3, 48, "waspada"),
        ("Keluhan publik bertambah", "complaint_growth", 50, 24, "waspada"),
        ("Isu menyeberang berita dan sosial", "cross_channel", 2, 48, "waspada"),
        ("Konten belum terverifikasi melonjak", "unverified_burst", 3, 24, "info"),
        ("Mention negatif terkait KPw", "kpw_negative", 3, 72, "waspada"),
        ("Volume mention pada jendela ramai", "volume_spike", 12, 24, "info"),
    )
    added = False
    for name, rule_type, threshold, window, severity in specs:
        if name in names:
            continue
        db.add(
            AlertRule(
                name=name,
                rule_type=rule_type,
                threshold=threshold,
                window_hours=window,
                severity=severity,
                keyword="",
                channel="dashboard",
                is_active=True,
            )
        )
        added = True
    if added:
        db.commit()


def evaluate_rules(db: Session) -> int:
    ensure_ews_rules(db)
    now = now_wib()
    created = 0
    for rule in db.query(AlertRule).filter(AlertRule.is_active.is_(True)).all():
        title, message, issue_id = _check(db, rule, now)
        if not title:
            continue
        start = (now - timedelta(hours=12)).replace(minute=0, second=0, microsecond=0)
        exists = (
            db.query(Alert)
            .filter(Alert.rule_id == rule.id, Alert.title == title, Alert.triggered_at >= start)
            .first()
        )
        if exists:
            continue
        db.add(
            Alert(
                rule_id=rule.id,
                title=title,
                message=message,
                severity=rule.severity,
                triggered_at=now,
                is_read=False,
                issue_id=issue_id,
            )
        )
        created += 1
    db.commit()
    return created


def ews_board(db: Session, alerts: list[Alert] | None = None, rules: list[AlertRule] | None = None) -> dict:
    """Ringkasan situasional untuk layar EWS."""
    if alerts is None:
        alerts = db.query(Alert).order_by(Alert.triggered_at.desc()).limit(50).all()
    if rules is None:
        rules = db.query(AlertRule).order_by(AlertRule.id).all()

    unread = [row for row in alerts if not row.is_read]
    by_sev = Counter(row.severity for row in unread)
    if by_sev.get("kritis"):
        level, label = "kritis", "Kritis — butuh perhatian segera"
        summary = "Ada sinyal kritis yang belum ditinjau. Prioritaskan klarifikasi internal dan verifikasi tautan."
    elif by_sev.get("waspada"):
        level, label = "waspada", "Waspada — pantau aktif"
        summary = "Ada tekanan narasi atau lonjakan yang perlu diikuti analis, belum tentu eskalasi publik."
    elif unread:
        level, label = "pantau", "Pantau — ada info baru"
        summary = "Ada pemberitahuan info. Cukup tinjau tanpa mengganggu alur kerja utama."
    else:
        level, label = "tenang", "Tenang — tidak ada alert terbuka"
        summary = "Tidak ada alert belum dibaca. Tetap jalankan siklus pantauan rutin."

    rule_by_id = {row.id: row for row in rules}
    focus = []
    for row in unread[:5]:
        rule = rule_by_id.get(row.rule_id) if row.rule_id else None
        focus.append(
            {
                "id": row.id,
                "title": row.title,
                "severity": row.severity,
                "rule_type": rule.rule_type if rule else "",
                "action": (PLAYBOOK.get(rule.rule_type, ("Tinjau sumber asli.", "Analis media"))[0] if rule else "Tinjau sumber asli."),
            }
        )

    active_watch = []
    for rule in rules:
        if not rule.is_active:
            continue
        meta = RULE_META.get(rule.rule_type, {})
        active_watch.append(
            {
                "id": rule.id,
                "name": rule.name,
                "rule_type": rule.rule_type,
                "label": meta.get("label") or rule.rule_type,
                "why": meta.get("why") or "",
                "severity": rule.severity,
                "threshold": rule.threshold,
                "window_hours": rule.window_hours,
            }
        )

    return {
        "level": level,
        "label": label,
        "summary": summary,
        "unread": len(unread),
        "by_severity": {
            "kritis": by_sev.get("kritis", 0),
            "waspada": by_sev.get("waspada", 0),
            "info": by_sev.get("info", 0),
        },
        "focus": focus,
        "watchpoints": active_watch[:12],
        "updated_at": now_wib().isoformat(timespec="minutes"),
    }


def enrich_alert(row: Alert, rule: AlertRule | None) -> dict:
    from app.services.serialize import alert_out

    data = alert_out(row)
    rule_type = rule.rule_type if rule else ""
    meta = RULE_META.get(rule_type, {})
    action, owner = PLAYBOOK.get(rule_type, ("Tinjau tautan sumber dan konteks isu.", "Analis media"))
    data.update(
        {
            "rule_type": rule_type,
            "rule_label": meta.get("label") or rule_type or "Aturan EWS",
            "why": meta.get("why") or "",
            "action": action,
            "owner": owner,
        }
    )
    return data


def _check(db: Session, rule: AlertRule, now) -> tuple[str, str, Optional[int]]:
    window_start = now - timedelta(hours=rule.window_hours)
    from app.services.blocklist import is_blocked, load_rules

    rules = load_rules(db)
    rows = [
        row
        for row in db.query(Mention).filter(Mention.published_at >= window_start).all()
        if not is_blocked(row.url, row.author_handle, row.author_name, row.source_name, row.title, rules)
    ]

    if rule.rule_type == "keyword_count":
        needle = (rule.keyword or "").casefold()
        hits = [row for row in rows if needle and needle in f"{row.title} {row.text}".casefold()]
        if len(hits) >= rule.threshold:
            return _hit(
                rule,
                f"Kata '{rule.keyword}' muncul {len(hits)} kali",
                f"Dalam {rule.window_hours} jam ada {len(hits)} mention memuat kata tersebut (ambang {rule.threshold:.0f}).",
                hits,
            )

    if rule.rule_type == "tier1_downside":
        hits = [row for row in rows if row.source_tier == 1 and row.stance == "downside"]
        if len(hits) >= rule.threshold:
            return _hit(
                rule,
                "Media arus utama mengangkat konten downside",
                f"{len(hits)} mention tier-1 bernada downside dalam {rule.window_hours} jam.",
                hits,
            )

    if rule.rule_type == "kpw_negative":
        hits = [row for row in rows if row.is_kpw and row.sentiment == "negatif"]
        if len(hits) >= rule.threshold:
            return _hit(
                rule,
                "Mention negatif terkait KPw meningkat",
                f"{len(hits)} mention KPw bernada negatif dalam {rule.window_hours} jam.",
                hits,
            )

    if rule.rule_type == "negative_growth":
        prev_start = window_start - timedelta(hours=rule.window_hours)
        prev_rows = _visible(db, prev_start, window_start, rules)
        now_neg = sum(1 for row in rows if row.sentiment == "negatif")
        prev_neg = sum(1 for row in prev_rows if row.sentiment == "negatif")
        if prev_neg == 0 and now_neg >= rule.threshold:
            growth = 100.0
        elif prev_neg:
            growth = (now_neg - prev_neg) / prev_neg * 100
        else:
            growth = 0
        if growth >= rule.threshold and now_neg > 0:
            hits = [row for row in rows if row.sentiment == "negatif"]
            return _hit(
                rule,
                f"Mention negatif naik {growth:.0f}%",
                f"Dari {prev_neg} menjadi {now_neg} pada jendela {rule.window_hours} jam (ambang {rule.threshold:.0f}%).",
                hits,
            )

    if rule.rule_type == "volume_spike":
        if len(rows) >= max(1, int(rule.threshold)):
            return _hit(
                rule,
                "Volume mention pada jendela aturan tergolong ramai",
                f"Ada {len(rows)} mention dalam {rule.window_hours} jam (ambang {rule.threshold:.0f}).",
                rows,
            )

    if rule.rule_type == "hoax_spread":
        hits = hoax_hits(rows)
        if len(hits) >= rule.threshold:
            return _hit(
                rule,
                f"Pola bahasa hoaks terbaca pada {len(hits)} konten",
                "Deteksi kata pada judul/cuplikan, bukan penetapan bahwa konten itu hoaks. " + _proof(hits),
                hits,
            )

    if rule.rule_type == "narrative_growth":
        prev_start = window_start - timedelta(hours=rule.window_hours)
        prev_rows = _visible(db, prev_start, window_start, rules)
        label, hits = fastest_narrative(rows, prev_rows)
        if label and len(hits) >= rule.threshold:
            return _hit(
                rule,
                f"Narasi tumbuh: {label}",
                f"{len(hits)} konten memuat pola narasi ini pada {rule.window_hours} jam terakhir. " + _proof(hits),
                hits,
            )

    if rule.rule_type == "complaint_growth":
        prev_start = window_start - timedelta(hours=rule.window_hours)
        prev_rows = _visible(db, prev_start, window_start, rules)
        now_n = complaint_count(rows)
        prev_n = complaint_count(prev_rows)
        growth = 100.0 if prev_n == 0 and now_n else ((now_n - prev_n) / prev_n * 100 if prev_n else 0)
        if growth >= rule.threshold and now_n > 0:
            keluhan = [row for row in rows if "keluhan" in voices_of(row)]
            return _hit(
                rule,
                f"Keluhan naik {growth:.0f}%",
                f"Dari {prev_n} menjadi {now_n} konten berkeluhan pada jendela {rule.window_hours} jam. " + _proof(keluhan),
                keluhan,
            )

    if rule.rule_type == "high_risk":
        hits = [row for row in rows if (row.risk_score or 0) >= rule.threshold]
        if len(hits) >= 2:
            top = max(hits, key=lambda row: row.risk_score or 0)
            return _hit(
                rule,
                f"{len(hits)} konten berisiko ≥ {rule.threshold:.0f}",
                f"Skor tertinggi {top.risk_score:.0f}. Prioritaskan tinjauan analis. " + _proof(hits),
                hits,
            )

    if rule.rule_type == "social_amplify":
        hits = [
            row
            for row in rows
            if (row.platform or "").casefold() in SOCIAL_PLATFORMS
            and (row.sentiment == "negatif" or row.stance == "downside")
        ]
        if len(hits) >= rule.threshold:
            platforms = sorted({(row.platform or "?").casefold() for row in hits})
            return _hit(
                rule,
                f"Sosial mengamplifikasi nada negatif ({len(hits)})",
                f"Platform: {', '.join(platforms)}. Jendela {rule.window_hours} jam. " + _proof(hits),
                hits,
            )

    if rule.rule_type == "currency_stress":
        hits = [row for row in rows if _currency_hit(row)]
        if len(hits) >= rule.threshold:
            return _hit(
                rule,
                f"Tekanan narasi rupiah/kurs ({len(hits)})",
                f"{len(hits)} konten memuat bahasa tekanan kurs/rupiah dalam {rule.window_hours} jam. " + _proof(hits),
                hits,
            )

    if rule.rule_type == "quote_pressure":
        hits = [
            row
            for row in rows
            if getattr(row, "quotes_bi", False) and (row.sentiment == "negatif" or row.stance == "downside")
        ]
        if len(hits) >= rule.threshold:
            return _hit(
                rule,
                f"Kutipan BI bernada negatif ({len(hits)})",
                f"{len(hits)} konten mengutip BI dengan nada negatif/downside. Cocokkan dengan pernyataan resmi. "
                + _proof(hits),
                hits,
            )

    if rule.rule_type == "unverified_burst":
        hits = [row for row in rows if getattr(row, "needs_verification", False)]
        if len(hits) >= rule.threshold:
            return _hit(
                rule,
                f"{len(hits)} konten belum terverifikasi",
                f"Ambang {rule.threshold:.0f} dalam {rule.window_hours} jam. Tahan komunikasi publik dulu. " + _proof(hits),
                hits,
            )

    if rule.rule_type == "cross_channel":
        by_issue: dict[int, set[str]] = defaultdict(set)
        sample: dict[int, list[Mention]] = defaultdict(list)
        for row in rows:
            if not row.issue_id:
                continue
            channel = "sosial" if (row.platform or "").casefold() in SOCIAL_PLATFORMS else "berita"
            by_issue[row.issue_id].add(channel)
            sample[row.issue_id].append(row)
        crossed = [issue_id for issue_id, channels in by_issue.items() if channels >= {"berita", "sosial"}]
        if len(crossed) >= rule.threshold:
            hits = []
            for issue_id in crossed[:3]:
                hits.extend(sample[issue_id][:2])
            return _hit(
                rule,
                f"{len(crossed)} isu menyeberang berita dan sosial",
                f"Pola eskalasi lintas kanal pada {rule.window_hours} jam. " + _proof(hits),
                hits,
                issue_id=crossed[0],
            )

    return "", "", None


def _hit(rule: AlertRule, title: str, body: str, hits: list[Mention], issue_id: Optional[int] = None) -> tuple[str, str, Optional[int]]:
    action, owner = PLAYBOOK.get(rule.rule_type, ("Tinjau tautan sumber.", "Analis media"))
    why = RULE_META.get(rule.rule_type, {}).get("why") or ""
    message = body
    if why:
        message += f" Mengapa penting: {why}"
    message += f" Tindakan disarankan ({owner}): {action}"
    if not issue_id and hits:
        issue_id = hits[0].issue_id
    return title, message, issue_id


def _currency_hit(row: Mention) -> bool:
    hay = f"{row.title}\n{row.text}\n{row.category or ''}".casefold()
    if any(term in hay for term in CURRENCY_TERMS):
        return True
    if row.category == "Rupiah/Kurs" and (row.sentiment == "negatif" or row.stance == "downside"):
        return True
    return False


def _visible(db: Session, start, end, rules) -> list[Mention]:
    from app.services.blocklist import is_blocked

    return [
        row
        for row in db.query(Mention).filter(Mention.published_at >= start, Mention.published_at < end).all()
        if not is_blocked(row.url, row.author_handle, row.author_name, row.source_name, row.title, rules)
    ]


def _proof(rows: list[Mention]) -> str:
    parts = [f"{row.title} — {row.url}" for row in rows[:3] if row.url]
    if not parts:
        return "Belum ada tautan bukti."
    return "Bukti: " + " | ".join(parts)
