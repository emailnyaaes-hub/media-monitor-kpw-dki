"""Dek rapat bergaya piramida. Angka hanya dari hitungan filter yang aktif.

Prakiraan, sasaran inflasi, dan pembanding daerah lain tidak diisi.
Bagian itu ditulis [data perlu dilengkapi].
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from sqlalchemy.orm import Session

from app.services import analytics
from app.services.clock import now_wib
from app.services.dss import list_advices

NAVY = RGBColor(0x0B, 0x1F, 0x3A)
INK = RGBColor(0x1A, 0x1D, 0x21)
GRAY = RGBColor(0x5C, 0x65, 0x70)
LINE = RGBColor(0xD9, 0xDE, 0xE3)
PALE = RGBColor(0xF4, 0xF5, 0xF6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x0E, 0x7C, 0x4A)
AMBER = RGBColor(0x8A, 0x5A, 0x00)
RED = RGBColor(0xB4, 0x33, 0x33)
GAP = "[data perlu dilengkapi]"

RINGKAS = ["cover", "exec", "kpi", "contribution", "actions"]


def build_preview(db: Session, window: dict, version: str, appendix: bool, lang: str) -> dict:
    deck = _model(db, window, version, appendix, lang)
    return {
        "filename": deck["filename"],
        "source_line": deck["source"],
        "version": version,
        "lang": lang,
        "appendix": appendix,
        "slides": [
            {
                "id": slide["id"],
                "number": index + 1,
                "section": slide["section"],
                "action_title": slide["title"],
                "visual": slide["visual"],
                "message": slide["message"],
                "so_what": slide["so_what"],
                "data_note": slide["data_note"],
                "speaker_note": slide["note"],
            }
            for index, slide in enumerate(deck["slides"])
        ],
    }


def render_pptx(db: Session, window: dict, version: str, appendix: bool, lang: str, edits: list[dict]) -> tuple[bytes, str]:
    deck = _model(db, window, version, appendix, lang)
    by_id = {item.get("id"): item for item in edits}
    for slide in deck["slides"]:
        edit = by_id.get(slide["id"]) or {}
        title = str(edit.get("action_title") or "").strip()
        so_what = edit.get("so_what")
        if title:
            slide["title"] = title[:240]
        if isinstance(so_what, str):
            slide["so_what"] = so_what.strip()[:400]
    return _pptx(deck), deck["filename"]


def _model(db: Session, window: dict, version: str, appendix: bool, lang: str) -> dict:
    overview = analytics.overview(db, window)
    issues = analytics.list_issues(db, window)[:5]
    advice = list_advices(db, {"category": window.get("category")} if window.get("category") else {}, top=5)
    grain = "week" if len(overview["trend"]) > 10 else "day"
    trend = analytics.trend(db, window, grain) if grain == "week" else overview["trend"]
    facts = _facts(overview, issues, advice["items"], trend, window, lang)
    slides = _slides(facts, lang)
    if version == "ringkas":
        slides = [slide for slide in slides if slide["id"] in RINGKAS]
    if not appendix:
        slides = [slide for slide in slides if slide["section"] != _t(lang, "Lampiran", "Appendix")]
    return {
        "filename": _filename(window),
        "source": facts["source"],
        "lang": lang,
        "facts": facts,
        "slides": slides,
    }


def _facts(overview: dict, issues: list[dict], advice: list[dict], trend: list[dict], window: dict, lang: str) -> dict:
    kpis = overview["kpis"]
    mention = kpis["total_mention"]
    net = kpis["net_sentiment"]
    critical = kpis["critical_issues"]
    share = kpis["sentiment_pct"]
    level = "kritis" if critical["value"] else "waspada" if share["negatif"] >= 25 else "aman"
    mover = next((row for row in overview["category_shift"] if row["delta"]), None)
    spikes = [point for point in trend if point.get("spike")]
    period = _range(overview["period"]["from"], overview["period"]["to"], lang)
    previous = _range(overview["previous_period"]["from"], overview["previous_period"]["to"], lang)
    theme = window.get("category") or window.get("location") or _t(lang, "seluruh kategori", "all categories")
    where = window.get("location") or _t(lang, "seluruh wilayah yang tertandai", "all tagged areas")
    return {
        "lang": lang,
        "period": period,
        "previous": previous,
        "theme": theme,
        "where": where,
        "level": level,
        "mention": mention["value"],
        "mention_prev": mention["previous"],
        "mention_delta": mention["value"] - mention["previous"],
        "net": net["value"],
        "net_prev": net["previous"],
        "net_delta": net["delta_points"],
        "critical": critical["value"],
        "critical_prev": critical["previous"],
        "share": share,
        "mover": mover,
        "shift": overview["category_shift"][:6],
        "areas": overview["areas"],
        "trend": trend,
        "spikes": spikes,
        "issues": issues,
        "advice": advice,
        "new_issues": sum(1 for item in issues if item.get("status") == "baru"),
        "source": _t(
            lang,
            f"Sumber: mention pihak luar pada Media Monitor, {period}. Bukan data BPS, SPI, atau PIHPS. Filter: {theme}; {where}.",
            f"Source: external mentions in Media Monitor, {period}. Not BPS, SPI, or PIHPS. Filter: {theme}; {where}.",
        ),
    }


def _slides(facts: dict, lang: str) -> list[dict]:
    level = _level_word(facts["level"], lang)
    mover = facts["mover"]
    mover_bit = (
        _t(
            lang,
            f"{mover['category']} berubah paling besar ({_signed(mover['delta'])} mention)",
            f"{mover['category']} moved the most ({_signed(mover['delta'])} mentions)",
        )
        if mover
        else _t(lang, "tidak ada kategori yang bergeser", "no category moved")
    )
    situation = _t(
        lang,
        f"Pada {facts['period']}, mention { _arah(facts['mention_delta'], lang) } dari {_num(facts['mention_prev'])} menjadi {_num(facts['mention'])}.",
        f"In {facts['period']}, mentions { _arah(facts['mention_delta'], lang) } from {_num(facts['mention_prev'])} to {_num(facts['mention'])}.",
    )
    slides = [
        _slide(
            "cover",
            _t(lang, "Pembuka", "Opening"),
            _t(lang, "Sampul", "Cover"),
            _t(
                lang,
                f"Persepsi publik di DKI Jakarta berstatus {level} pada {facts['period']}",
                f"Public perception in Jakarta is {level} for {facts['period']}",
            ),
            situation,
            "",
            _t(lang, "Fakta dari hitungan mention. Bukan proyeksi.", "Count of mentions. Not a forecast."),
            _t(lang, "Sebut status, periode, dan bahwa ini bahan internal.", "State the status, the period, and that the deck is internal."),
        ),
        _slide(
            "exec",
            _t(lang, "Ringkasan", "Summary"),
            _t(lang, "Ringkasan eksekutif", "Executive summary"),
            _t(
                lang,
                f"Status {level}: mention {_num(facts['mention'])}, sentimen bersih {_num(facts['net'])} poin, {mover_bit}",
                f"Status {level}: {_num(facts['mention'])} mentions, net sentiment {_num(facts['net'])} points, {mover_bit}",
            ),
            situation,
            _t(
                lang,
                "Keputusan yang diminta: meninjau opsi yang punya sumber, atau menunda bila bukti belum cukup. Deck ini tidak menetapkan kebijakan.",
                "Decision requested: review options that cite a source, or defer when evidence is thin. This deck does not set policy.",
            ),
            _t(lang, "Tiga angka di atas sama dengan kartu Ringkasan.", "The three figures match the Overview cards."),
            _t(lang, "Bacakan kesimpulan, lalu satu keputusan yang diminta.", "Read the conclusion, then the decision requested."),
        ),
        _slide(
            "kpi",
            _t(lang, "Ringkasan", "Summary"),
            _t(lang, "Empat indikator", "Four indicators"),
            _t(
                lang,
                f"Empat indikator persepsi: mention {_num(facts['mention'])}, bersih {_num(facts['net'])}, isu kritis {_num(facts['critical'])}, negatif {_pct(facts['share']['negatif'])}",
                f"Four perception indicators: {_num(facts['mention'])} mentions, net {_num(facts['net'])}, {_num(facts['critical'])} critical issues, {_pct(facts['share']['negatif'])} negative",
            ),
            _t(lang, "Panah menunjukkan arah terhadap periode sebelumnya. Warna hanya pada status.", "Arrows show the change versus the previous period. Color is used only for status."),
            _t(
                lang,
                f"Ambang tampilan: negatif 25% waspada, 40% atau ada isu kritis berarti kritis. Kini {level}.",
                f"Display threshold: 25% negative is watch, 40% or any critical issue is critical. Now {level}.",
            ),
            _t(lang, "Selisih buah dipakai bila pembanding di bawah 5.", "The absolute change is shown when the base is below 5."),
            _t(lang, "Tunjuk satu kartu yang statusnya bukan aman.", "Point to the card whose status is not calm."),
        ),
        _slide(
            "trend",
            _t(lang, "Kondisi", "Situation"),
            _t(lang, "Grafik kolom bertumpuk", "Stacked column chart"),
            _t(
                lang,
                f"Volume mention { _arah(facts['mention_delta'], lang) } dibanding {facts['previous']}"
                + (f", dengan lonjakan pada {_num(len(facts['spikes']))} ember waktu" if facts["spikes"] else ""),
                f"Mention volume { _arah(facts['mention_delta'], lang) } versus {facts['previous']}"
                + (f", with a spike in {_num(len(facts['spikes']))} time buckets" if facts["spikes"] else ""),
            ),
            situation,
            _t(
                lang,
                "Garis prakiraan dan interval kepercayaan tidak digambar. " + GAP,
                "No forecast line or confidence band is drawn. " + GAP,
            ),
            _t(lang, "Fakta. Tiap batang adalah jumlah mention pada ember waktu itu.", "Fact. Each column is the mention count in that time bucket."),
            _t(lang, "Jelaskan arah volume, lalu sebut bahwa prakiraan belum tersedia.", "Explain the volume direction, then say the forecast is not available."),
        ),
        _slide(
            "contribution",
            _t(lang, "Penyebab", "Cause"),
            _t(lang, "Grafik batang kontribusi", "Contribution bar chart"),
            _t(
                lang,
                f"Perubahan volume didorong oleh {mover['category']} ({_signed(mover['delta'])} mention)" if mover else "Tidak ada kategori yang mengubah volume dibanding periode lalu",
                f"The volume change is led by {mover['category']} ({_signed(mover['delta'])} mentions)" if mover else "No category changed volume versus the previous period",
            ),
            mover_bit[0].upper() + mover_bit[1:] + ".",
            _t(
                lang,
                "Ini selisih jumlah mention, bukan kontribusi harga atau inflasi.",
                "This is the change in mention counts, not a price or inflation contribution.",
            ),
            _t(lang, "Enam kategori dengan selisih mutlak terbesar.", "The six categories with the largest absolute change."),
            _t(lang, "Sebut satu kategori yang batangnya paling panjang.", "Name the category with the longest bar."),
        ),
        _slide(
            "composition",
            _t(lang, "Komposisi", "Mix"),
            _t(lang, "Grafik kolom komposisi", "Composition column chart"),
            _t(
                lang,
                f"Komposisi kini: positif {_pct(facts['share']['positif'])}, netral {_pct(facts['share']['netral'])}, negatif {_pct(facts['share']['negatif'])}",
                f"Current mix: positive {_pct(facts['share']['positif'])}, neutral {_pct(facts['share']['netral'])}, negative {_pct(facts['share']['negatif'])}",
            ),
            _t(lang, "Bandingkan dengan periode lalu pada batang kedua.", "Compare with the previous period on the second column."),
            _t(lang, "Pembanding nasional dan provinsi lain: " + GAP, "National and peer-province comparisons: " + GAP),
            _t(lang, "Tinggi batang adalah pangsa yang sama dengan kartu komposisi di dashboard.", "Column height is the same share shown on the dashboard composition card."),
            _t(lang, "Bacakan tiga pangsa, lalu sebut pembanding yang belum ada.", "Read the three shares, then the comparisons that are missing."),
        ),
        _slide(
            "issues",
            _t(lang, "Isu", "Issues"),
            _t(lang, "Tabel isu", "Issue table"),
            _issue_title(facts, lang),
            _t(lang, "Maksimal lima isu menurut skor risiko pada filter ini.", "Up to five issues by risk score in this filter."),
            _t(lang, "Buka sumber asli di dashboard sebelum isu dibawa ke rapat.", "Open the original source in the dashboard before taking an issue to the meeting."),
            _t(lang, "Risiko adalah skor persepsi, bukan keputusan kebijakan.", "Risk is a perception score, not a policy decision."),
            _t(lang, "Sebut isu teratas dan statusnya.", "Name the top issue and its status."),
        ),
        _slide(
            "areas",
            _t(lang, "Wilayah", "Areas"),
            _t(lang, "Tabel wilayah", "Area table"),
            _area_title(facts, lang),
            _t(lang, "Jumlah adalah mention yang menyebut nama wilayah.", "Counts are mentions that name the area."),
            _t(lang, "Peta batas administrasi tidak dipakai. " + GAP, "Official boundaries are not used. " + GAP),
            _t(lang, "Nol berarti belum ada penanda, bukan angka ekonomi wilayah.", "Zero means no place tag, not an economic statistic."),
            _t(lang, "Sebut wilayah yang angkanya bukan nol, bila ada.", "Name any area whose count is not zero."),
        ),
        _slide(
            "warning",
            _t(lang, "Peringatan", "Warning"),
            _t(lang, "Tabel ambang", "Threshold table"),
            _t(
                lang,
                f"Peringatan dini berstatus {level}: isu kritis {_num(facts['critical'])}, negatif {_pct(facts['share']['negatif'])}, lonjakan {_num(len(facts['spikes']))}",
                f"Early warning is {level}: {_num(facts['critical'])} critical issues, {_pct(facts['share']['negatif'])} negative, {_num(len(facts['spikes']))} spikes",
            ),
            _t(lang, "Pemicu yang menyala perlu verifikasi manusia.", "A triggered signal still needs a human check."),
            _t(lang, "Ambang 25% dan risiko 75 adalah ambang tampilan, belum ketetapan resmi.", "The 25% and risk-75 marks are display thresholds, not a formal rule."),
            _t(lang, "Status dihitung dari filter aktif.", "Status is calculated from the active filter."),
            _t(lang, "Sebut pemicu yang menyala dan yang tidak.", "State which triggers are on and which are off."),
        ),
        _slide(
            "scenario",
            _t(lang, "Skenario", "Scenarios"),
            _t(lang, "Tabel skenario", "Scenario table"),
            _t(
                lang,
                f"Baseline persepsi tercatat; jalur optimis dan pesimis {GAP}",
                f"The perception baseline is recorded; optimistic and pessimistic paths are {GAP}",
            ),
            _t(lang, "Hanya kolom baseline yang berisi angka dashboard.", "Only the baseline column contains dashboard figures."),
            _t(lang, "Asumsi: optimis dan pesimis tidak dihitung, jadi tidak boleh dibaca sebagai proyeksi.", "Assumption: optimistic and pessimistic paths are not calculated and are not forecasts."),
            _t(lang, "Label: fakta pada baseline, bukan proyeksi pada dua kolom lain.", "Label: fact in the baseline, not a forecast in the other columns."),
            _t(lang, "Tekankan bahwa dua kolom kanan sengaja kosong dari angka.", "Stress that the two right-hand columns deliberately have no figures."),
        ),
        _slide(
            "actions",
            _t(lang, "Rekomendasi", "Recommendations"),
            _t(lang, "Tabel aksi", "Action table"),
            _action_title(facts, lang),
            _t(lang, "Setiap baris yang menyarankan tindak punya tautan di Pusat Saran.", "Each action row has a source link in the advice centre."),
            _t(lang, "Target waktu tidak tersimpan. Kolom waktu berisi " + GAP, "No due date is stored. The timing column says " + GAP),
            _t(lang, "Saran mengikuti siklus terakhir, belum disaring menurut tanggal. Bukti tipis tetap berbunyi perlu verifikasi.", "Advice follows the latest cycle and is not date-filtered. Thin evidence stays worded as needs verification."),
            _t(lang, "Minta keputusan pada satu baris, bukan pada seluruh tabel.", "Ask for a decision on one row, not the whole table."),
        ),
        _slide(
            "next",
            _t(lang, "Langkah", "Next steps"),
            _t(lang, "Tiga jangka", "Three horizons"),
            _t(
                lang,
                f"Langkah terdekat: verifikasi {_num(facts['new_issues'])} isu berstatus baru pada daftar teratas; jangka berikut {GAP}",
                f"Nearest step: verify {_num(facts['new_issues'])} issues still marked new in the top list; later horizons are {GAP}",
            ),
            _t(lang, "30 hari hanya memuat pekerjaan verifikasi yang sudah terlihat di data.", "The 30-day line only covers verification work already visible in the data."),
            _t(lang, "Jangka 60 dan 90 hari tidak diisi jadwal rekayasa.", "The 60- and 90-day lines are not filled with an invented timetable."),
            _t(lang, "Usulan proses, bukan kalender resmi KPw.", "A process suggestion, not an official KPw calendar."),
            _t(lang, "Tutup dengan satu pemilik yang perlu meninjau, bila unitnya terisi.", "Close with one owner who should review, if a unit is recorded."),
        ),
        _slide(
            "method",
            _t(lang, "Lampiran", "Appendix"),
            _t(lang, "Catatan metode", "Method note"),
            _t(lang, "Angka deck ini menelusuri mention unik pihak luar pada filter yang sama dengan dashboard", "Figures in this deck trace to unique external mentions on the same filter as the dashboard"),
            _t(lang, "Kanal resmi Bank Indonesia tidak dihitung.", "Official Bank Indonesia channels are excluded."),
            _t(lang, "Sentimen bersih = pangsa positif dikurangi pangsa negatif, dalam poin.", "Net sentiment = positive share minus negative share, in points."),
            _t(lang, "Isu kritis = risiko minimal 75, nada downside, status belum selesai.", "A critical issue has risk of at least 75, a downside stance, and is not closed."),
            _t(lang, "Lonjakan = jumlah pada ember >= rata-rata + 2 simpangan baku dan minimal 8, bila ada minimal 5 ember.", "A spike is a bucket at least at the mean plus 2 standard deviations and at least 8, when there are at least 5 buckets."),
        ),
        _slide(
            "glossary",
            _t(lang, "Lampiran", "Appendix"),
            _t(lang, "Glosarium", "Glossary"),
            _t(lang, "Istilah pada deck ini punya arti operasional yang sempit", "Terms in this deck have a narrow operational meaning"),
            _t(lang, "Persepsi bukan inflasi, kredit, atau nilai transaksi.", "Perception is not inflation, credit, or transaction value."),
            "yoy / mtm: " + GAP,
            _t(lang, "RAG: aman, waspada, kritis, selalu bersama kata dan tanda.", "RAG: calm, watch, critical, always with a word and a mark."),
            _t(lang, "Bila istilah dibandingkan dengan seri resmi, seri itu belum terhubung.", "Where a term is compared with an official series, that series is not connected."),
        ),
        _slide(
            "detail",
            _t(lang, "Lampiran", "Appendix"),
            _t(lang, "Tabel selisih kategori", "Category-change table"),
            _t(lang, "Lampiran mengulang selisih mention per kategori agar dapat ditelusuri", "The appendix repeats the mention change by category so it can be traced"),
            _t(lang, "Kolom kini dan lalu berasal dari dua jendela yang sama panjang.", "The current and previous columns come from two windows of equal length."),
            "",
            _t(lang, "Tidak ada angka di luar hitungan itu.", "There is no figure outside that count."),
            _t(lang, "Gunakan slide ini hanya bila ada pertanyaan soal satu kategori.", "Use this slide only if someone asks about one category."),
        ),
    ]
    return slides


def _slide(sid: str, section: str, visual: str, title: str, message: str, so_what: str, data_note: str, note: str) -> dict:
    return {
        "id": sid,
        "section": section,
        "visual": visual,
        "title": title,
        "message": message,
        "so_what": so_what,
        "data_note": data_note,
        "note": note,
    }


def _pptx(deck: dict) -> bytes:
    facts = deck["facts"]
    slides = deck["slides"]
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    presentation.core_properties.title = slides[0]["title"] if slides else "Media Monitor"
    presentation.core_properties.subject = "Untuk Internal"
    presentation.core_properties.category = "KPw BI DKI Jakarta"
    blank = presentation.slide_layouts[6]
    total = len(slides)
    for index, spec in enumerate(slides, start=1):
        slide = presentation.slides.add_slide(blank)
        _paint(slide, spec, facts, index, total, deck["source"])
        notes = slide.notes_slide.notes_text_frame
        notes.text = spec["note"]
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def _paint(slide, spec: dict, facts: dict, index: int, total: int, source: str) -> None:
    _chrome(slide, spec, index, total, source)
    kind = spec["id"]
    if kind == "cover":
        _cover(slide, spec, facts)
    elif kind == "exec":
        _exec(slide, spec, facts)
    elif kind == "kpi":
        _kpis(slide, spec, facts)
    elif kind == "trend":
        _trend(slide, spec, facts)
    elif kind == "contribution":
        _contribution(slide, spec, facts)
    elif kind == "composition":
        _composition(slide, spec, facts)
    elif kind == "issues":
        _issue_table(slide, facts)
    elif kind == "areas":
        _area_table(slide, facts)
    elif kind == "warning":
        _warning(slide, facts)
    elif kind == "scenario":
        _scenario(slide, facts)
    elif kind == "actions":
        _actions(slide, facts)
    elif kind == "next":
        _next(slide, facts)
    elif kind == "detail":
        _detail(slide, facts)
    else:
        _bullets(slide, [spec["message"], spec["so_what"], spec["data_note"]])
    if spec["so_what"] and kind not in {"cover", "exec", "kpi"}:
        _callout(slide, spec["so_what"])


def _chrome(slide, spec: dict, index: int, total: int, source: str) -> None:
    _text(slide, 0.5, 0.18, 8, 0.28, f"{index:02d}    {spec['section']}", 12, NAVY, bold=True)
    _text(slide, 10.4, 0.18, 2.4, 0.28, f"{index} / {total}", 12, GRAY, align=PP_ALIGN.RIGHT)
    _text(slide, 0.5, 0.48, 12.3, 0.95, spec["title"], 24, NAVY, bold=True, font="Georgia")
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.48), Inches(12.3), Emu(9525))
    line.fill.solid()
    line.fill.fore_color.rgb = LINE
    line.line.fill.background()
    _text(slide, 0.5, 7.12, 11.2, 0.28, source, 12, GRAY)
    _text(slide, 11.2, 7.12, 1.6, 0.28, "Internal", 12, GRAY, align=PP_ALIGN.RIGHT)


def _cover(slide, spec: dict, facts: dict) -> None:
    _text(slide, 0.5, 2.0, 8, 0.4, "KPw BI DKI Jakarta", 16, GRAY)
    _text(slide, 0.5, 2.5, 8, 0.4, facts["period"], 18, NAVY, bold=True)
    _text(slide, 0.5, 3.1, 8, 0.4, _t(facts["lang"], f"Disusun {now_wib().strftime('%d %b %Y')} WIB", f"Prepared {now_wib().strftime('%d %b %Y')} WIB"), 14, INK)
    _text(slide, 0.5, 3.6, 8, 0.4, "Untuk Internal", 14, NAVY, bold=True)
    _text(slide, 0.5, 4.3, 8, 1.2, spec["message"], 16, INK)


def _exec(slide, spec: dict, facts: dict) -> None:
    lang = facts["lang"]
    bullets = [
        spec["message"],
        _t(lang, f"Sentimen bersih {_num(facts['net'])} poin ({_signed(facts['net_delta'])} poin).", f"Net sentiment {_num(facts['net'])} points ({_signed(facts['net_delta'])} points)."),
        _t(lang, f"Isu kritis terbuka: {_num(facts['critical'])}.", f"Open critical issues: {_num(facts['critical'])}."),
        _t(lang, f"Pangsa negatif {_pct(facts['share']['negatif'])}.", f"Negative share {_pct(facts['share']['negatif'])}."),
    ]
    _bullets(slide, bullets[:5], width=8.2)
    _box(slide, 0.5, 5.15, 12.3, 1.7, spec["so_what"], NAVY)


def _kpis(slide, spec: dict, facts: dict) -> None:
    lang = facts["lang"]
    cards = [
        (_t(lang, "Mention", "Mentions"), _num(facts["mention"]), _move(facts["mention_delta"], lang), None),
        (_t(lang, "Sentimen bersih", "Net sentiment"), _num(facts["net"]), _t(lang, f"{_signed(facts['net_delta'])} poin", f"{_signed(facts['net_delta'])} pts"), _level_word(_level_from_share(facts["share"]["negatif"]), lang)),
        (_t(lang, "Isu kritis", "Critical issues"), _num(facts["critical"]), _move(facts["critical"] - facts["critical_prev"], lang), _level_word("kritis" if facts["critical"] else "aman", lang)),
        (_t(lang, "Pangsa negatif", "Negative share"), _pct(facts["share"]["negatif"]), _t(lang, f"lalu {_pct(facts['share']['previous']['negatif'])}", f"prev. {_pct(facts['share']['previous']['negatif'])}"), _level_word(_level_from_share(facts["share"]["negatif"]), lang)),
    ]
    for index, (label, value, delta, status) in enumerate(cards):
        left = 0.5 + index * 3.15
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(1.8), Inches(3.0), Inches(2.3))
        shape.fill.solid()
        shape.fill.fore_color.rgb = WHITE
        shape.line.color.rgb = LINE
        _text(slide, left + 0.15, 1.95, 2.7, 0.3, label, 13, GRAY)
        _text(slide, left + 0.15, 2.3, 2.7, 0.6, value, 28, NAVY, bold=True)
        _text(slide, left + 0.15, 3.05, 2.7, 0.35, delta, 13, GRAY)
        if status:
            _text(slide, left + 0.15, 3.45, 2.7, 0.35, _mark(status, lang), 13, _rag_color(status), bold=True)
    _text(slide, 0.5, 4.4, 12.3, 0.9, spec["so_what"], 14, INK)


def _trend(slide, spec: dict, facts: dict) -> None:
    rows = facts["trend"]
    if not rows:
        _bullets(slide, [spec["message"]])
        return
    data = CategoryChartData()
    data.categories = [_short_day(row["date"]) for row in rows]
    data.add_series(_t(facts["lang"], "Positif", "Positive"), tuple(row["positif"] for row in rows))
    data.add_series(_t(facts["lang"], "Netral", "Neutral"), tuple(row["netral"] for row in rows))
    data.add_series(_t(facts["lang"], "Negatif", "Negative"), tuple(row["negatif"] for row in rows))
    chart = _add_chart(slide, XL_CHART_TYPE.COLUMN_STACKED, data, 0.4, 1.7, 8.7, 5.1)
    _paint_series(chart, [GREEN, RGBColor(0x8B, 0x97, 0xA3), RED])
    chart.plots[0].has_data_labels = len(rows) <= 8


def _contribution(slide, spec: dict, facts: dict) -> None:
    rows = [row for row in facts["shift"] if row["delta"]]
    if not rows:
        _bullets(slide, [spec["message"]])
        return
    data = CategoryChartData()
    data.categories = [row["category"] for row in rows]
    data.add_series(_t(facts["lang"], "Selisih mention", "Mention change"), tuple(row["delta"] for row in rows))
    chart = _add_chart(slide, XL_CHART_TYPE.BAR_CLUSTERED, data, 0.4, 1.7, 8.7, 5.1)
    _paint_series(chart, [NAVY])
    chart.plots[0].has_data_labels = True


def _composition(slide, spec: dict, facts: dict) -> None:
    share = facts["share"]
    data = CategoryChartData()
    data.categories = [_t(facts["lang"], "Kini", "Current"), _t(facts["lang"], "Lalu", "Previous")]
    data.add_series(_t(facts["lang"], "Positif", "Positive"), (share["positif"], share["previous"]["positif"]))
    data.add_series(_t(facts["lang"], "Netral", "Neutral"), (share["netral"], share["previous"]["netral"]))
    data.add_series(_t(facts["lang"], "Negatif", "Negative"), (share["negatif"], share["previous"]["negatif"]))
    chart = _add_chart(slide, XL_CHART_TYPE.COLUMN_STACKED, data, 0.4, 1.7, 8.7, 5.1)
    _paint_series(chart, [GREEN, RGBColor(0x8B, 0x97, 0xA3), RED])
    chart.plots[0].has_data_labels = True


def _issue_table(slide, facts: dict) -> None:
    lang = facts["lang"]
    header = [_t(lang, "Isu", "Issue"), _t(lang, "Status", "Status"), _t(lang, "Risiko", "Risk"), _t(lang, "Mention", "Mentions")]
    body = []
    for item in facts["issues"]:
        status = _level_word("kritis" if item.get("is_critical") else "waspada" if item.get("stance") == "downside" and item.get("risk_score", 0) >= 50 else "aman", lang)
        body.append([_clip(item["title"], 70), _mark(status, lang), _num(round(item["risk_score"])), _num(item["mention_count"])])
    if not body:
        body = [[_t(lang, "Belum ada isu pada filter ini.", "No issues in this filter."), "", "", ""]]
    _table(slide, header, body, 0.5, 1.75, 8.6)


def _area_table(slide, facts: dict) -> None:
    lang = facts["lang"]
    header = [_t(lang, "Wilayah", "Area"), _t(lang, "Mention", "Mentions"), _t(lang, "Status", "Status")]
    body = []
    for area in facts["areas"]:
        if area["count"] == 0:
            status = _t(lang, "Belum ada", "None")
        elif area["count"] < 3 or area["negatif"] is None:
            status = _t(lang, "Belum cukup", "Too few")
        else:
            status = _mark(_level_word(_level_from_share(area["negatif"]), lang), lang)
        body.append([area["name"], _num(area["count"]), status])
    _table(slide, header, body, 0.5, 1.75, 8.6)


def _warning(slide, facts: dict) -> None:
    lang = facts["lang"]
    negatif = facts["share"]["negatif"]
    header = [_t(lang, "Indikator", "Indicator"), _t(lang, "Ambang", "Threshold"), _t(lang, "Kini", "Now"), _t(lang, "Pemicu", "Trigger")]
    body = [
        [_t(lang, "Isu kritis terbuka", "Open critical issues"), _t(lang, "lebih dari 0", "above 0"), _num(facts["critical"]), _t(lang, "Menyala", "On") if facts["critical"] else _t(lang, "Tidak", "Off")],
        [_t(lang, "Pangsa negatif", "Negative share"), "25% / 40%", _pct(negatif), _t(lang, "Menyala", "On") if negatif >= 25 else _t(lang, "Tidak", "Off")],
        [_t(lang, "Lonjakan volume", "Volume spike"), _t(lang, "rata-rata + 2 simpangan, min. 8", "mean + 2 sd, min. 8"), _num(len(facts["spikes"])), _t(lang, "Menyala", "On") if facts["spikes"] else _t(lang, "Tidak", "Off")],
    ]
    _table(slide, header, body, 0.5, 1.75, 8.6)


def _scenario(slide, facts: dict) -> None:
    lang = facts["lang"]
    header = [_t(lang, "Indikator", "Indicator"), _t(lang, "Baseline (fakta)", "Baseline (fact)"), _t(lang, "Optimis", "Upside"), _t(lang, "Pesimis", "Downside")]
    body = [
        [_t(lang, "Mention", "Mentions"), _num(facts["mention"]), GAP, GAP],
        [_t(lang, "Sentimen bersih", "Net sentiment"), _num(facts["net"]), GAP, GAP],
        [_t(lang, "Isu kritis", "Critical issues"), _num(facts["critical"]), GAP, GAP],
    ]
    _table(slide, header, body, 0.5, 1.75, 8.6)
    _text(slide, 0.5, 4.6, 8.4, 0.8, _t(lang, "Asumsi: dua kolom kanan bukan proyeksi dan tidak dihitung.", "Assumption: the two right-hand columns are not a forecast and are not calculated."), 14, INK)


def _actions(slide, facts: dict) -> None:
    lang = facts["lang"]
    header = [_t(lang, "Opsi", "Option"), _t(lang, "Pemilik", "Owner"), _t(lang, "Prioritas", "Priority"), _t(lang, "Waktu", "Timing")]
    body = []
    for item in facts["advice"][:5]:
        text = _t(lang, "Data belum cukup, perlu verifikasi.", "Evidence is thin and needs a check.") if item.get("insufficient") else item.get("recommendation") or item.get("title")
        body.append([_clip(text, 80), _clip(item.get("unit") or GAP, 28), str(item.get("urgency") or ""), GAP])
    if not body:
        body = [[_t(lang, "Belum ada saran dengan bukti pada siklus ini.", "No sourced advice in this cycle."), GAP, "", GAP]]
    _table(slide, header, body, 0.5, 1.75, 8.6)


def _next(slide, facts: dict) -> None:
    lang = facts["lang"]
    header = [_t(lang, "Jangka", "Horizon"), _t(lang, "Langkah", "Step"), _t(lang, "Label", "Label")]
    body = [
        ["30", _t(lang, f"Verifikasi {_num(facts['new_issues'])} isu berstatus baru pada daftar teratas.", f"Verify {_num(facts['new_issues'])} issues still marked new in the top list."), _t(lang, "Usulan proses", "Process suggestion")],
        ["60", GAP, _t(lang, "Bukan jadwal resmi", "Not an official timetable")],
        ["90", GAP, _t(lang, "Bukan jadwal resmi", "Not an official timetable")],
    ]
    _table(slide, header, body, 0.5, 1.75, 8.6)


def _detail(slide, facts: dict) -> None:
    lang = facts["lang"]
    header = [_t(lang, "Kategori", "Category"), _t(lang, "Kini", "Current"), _t(lang, "Lalu", "Previous"), _t(lang, "Selisih", "Change")]
    body = [[row["category"], _num(row["current"]), _num(row["previous"]), _signed(row["delta"])] for row in facts["shift"]]
    if not body:
        body = [[GAP, "", "", ""]]
    _table(slide, header, body, 0.5, 1.75, 12.3)


def _add_chart(slide, chart_type, data, left, top, width, height):
    frame = slide.shapes.add_chart(chart_type, Inches(left), Inches(top), Inches(width), Inches(height), data)
    chart = frame.chart
    chart.has_legend = False
    chart.has_title = False
    _quiet_axis(chart.value_axis)
    _quiet_axis(chart.category_axis)
    plot = chart.plots[0]
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.font.size = Pt(12)
    labels.font.name = "Calibri"
    labels.font.color.rgb = NAVY
    labels.font.bold = True
    return chart


def _quiet_axis(axis) -> None:
    axis.has_major_gridlines = False
    axis.has_minor_gridlines = False
    axis.tick_labels.font.size = Pt(12)
    axis.tick_labels.font.name = "Calibri"
    axis.tick_labels.font.color.rgb = GRAY
    axis.format.line.color.rgb = LINE


def _paint_series(chart, colors: list[RGBColor]) -> None:
    for series, color in zip(chart.series, colors):
        fill = series.format.fill
        fill.solid()
        fill.fore_color.rgb = color
        solid = series.format._element.find(qn("c:spPr"))
        if solid is not None:
            scheme = solid.find(".//" + qn("a:schemeClr"))
            if scheme is not None:
                scheme.getparent().remove(scheme)


def _table(slide, header: list[str], body: list[list[str]], left: float, top: float, width: float) -> None:
    rows = 1 + len(body)
    cols = len(header)
    table_shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top), Inches(width), Inches(0.38 * rows))
    table = table_shape.table
    for col, value in enumerate(header):
        cell = table.cell(0, col)
        cell.text = value
        _style_cell(cell, 12, NAVY, True, PALE)
    for row_index, row in enumerate(body, start=1):
        for col, value in enumerate(row):
            cell = table.cell(row_index, col)
            cell.text = str(value)
            _style_cell(cell, 12, INK, False, WHITE)


def _style_cell(cell, size: int, color: RGBColor, bold: bool, fill: RGBColor) -> None:
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    for paragraph in cell.text_frame.paragraphs:
        paragraph.font.size = Pt(size)
        paragraph.font.name = "Calibri"
        paragraph.font.bold = bold
        paragraph.font.color.rgb = color


def _bullets(slide, lines: list[str], width: float = 8.4) -> None:
    kept = [line for line in lines if line]
    _text(slide, 0.55, 1.75, width, 3.3, "\n".join(f"•  {line}" for line in kept[:5]), 16, INK)


def _callout(slide, text: str) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(9.35), Inches(1.75), Inches(3.5), Inches(4.6))
    shape.fill.solid()
    shape.fill.fore_color.rgb = PALE
    shape.line.fill.background()
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.16)
    frame.margin_right = Inches(0.16)
    paragraph = frame.paragraphs[0]
    paragraph.text = "So what"
    paragraph.font.size = Pt(12)
    paragraph.font.bold = True
    paragraph.font.name = "Calibri"
    paragraph.font.color.rgb = NAVY
    body = frame.add_paragraph()
    body.text = text
    body.font.size = Pt(14)
    body.font.name = "Calibri"
    body.font.color.rgb = INK


def _box(slide, left, top, width, height, text: str, color: RGBColor) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = PALE
    shape.line.color.rgb = color
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.18)
    frame.margin_right = Inches(0.18)
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.size = Pt(14)
    paragraph.font.name = "Calibri"
    paragraph.font.color.rgb = INK


def _text(slide, left, top, width, height, text, size, color, bold=False, align=PP_ALIGN.LEFT, font="Calibri") -> None:
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    for index, line in enumerate(str(text).split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.alignment = align
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.name = font
        paragraph.font.color.rgb = color


def _filename(window: dict) -> str:
    theme = window.get("category") or window.get("location") or "Media"
    theme = re.sub(r"[^A-Za-z0-9]+", "-", theme).strip("-")[:40] or "Media"
    start = window["date_from"].strftime("%Y%m%d")
    end = window["date_to"].strftime("%Y%m%d")
    stamp = now_wib().strftime("%Y%m%d")
    return f"BI-DKI_{theme}_{start}-{end}_{stamp}.pptx"


def _range(start: str, end: str, lang: str) -> str:
    left = _day(start)
    right = _day(end)
    return f"{left}–{right}" if lang == "id" else f"{left} to {right}"


def _day(iso: str) -> str:
    moment = datetime.strptime(iso[:10], "%Y-%m-%d")
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{moment.day} {months[moment.month - 1]} {moment.year}"


def _short_day(iso: str) -> str:
    moment = datetime.strptime(iso[:10], "%Y-%m-%d")
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{moment.day} {months[moment.month - 1]}"


def _num(value: float | int) -> str:
    return f"{int(round(value)):,}".replace(",", ".")


def _pct(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + "%"


def _signed(value: float) -> str:
    number = _num(abs(value))
    if value > 0:
        return f"+{number}"
    if value < 0:
        return f"-{number}"
    return "0"


def _arah(delta: float, lang: str) -> str:
    if delta > 0:
        return _t(lang, "naik", "rose")
    if delta < 0:
        return _t(lang, "turun", "fell")
    return _t(lang, "tetap", "was unchanged")


def _move(delta: float, lang: str) -> str:
    word = "▲" if delta > 0 else "▼" if delta < 0 else "–"
    return f"{word} {_arah(delta, lang)} {_num(abs(delta))}"


def _level_from_share(negatif: float) -> str:
    if negatif >= 40:
        return "kritis"
    if negatif >= 25:
        return "waspada"
    return "aman"


def _level_word(level: str, lang: str) -> str:
    table = {
        "id": {"aman": "Aman", "waspada": "Waspada", "kritis": "Kritis"},
        "en": {"aman": "Calm", "waspada": "Watch", "kritis": "Critical"},
    }
    return table[lang][level]


def _mark(word: str, lang: str) -> str:
    marks = {
        "Aman": "● Aman",
        "Calm": "● Calm",
        "Waspada": "– Waspada",
        "Watch": "– Watch",
        "Kritis": "▲ Kritis",
        "Critical": "▲ Critical",
    }
    return marks.get(word, word)


def _rag_color(word: str) -> RGBColor:
    if word in {"Kritis", "Critical"}:
        return RED
    if word in {"Waspada", "Watch"}:
        return AMBER
    if word in {"Aman", "Calm"}:
        return GREEN
    return GRAY


def _issue_title(facts: dict, lang: str) -> str:
    if not facts["issues"]:
        return _t(lang, "Tidak ada isu terbuka pada filter ini", "No open issue in this filter")
    top = facts["issues"][0]
    return _t(
        lang,
        f"Isu teratas berisiko {_num(round(top['risk_score']))}: {_clip(top['title'], 80)}",
        f"Top issue scores {_num(round(top['risk_score']))}: {_clip(top['title'], 80)}",
    )


def _area_title(facts: dict, lang: str) -> str:
    ranked = sorted(facts["areas"], key=lambda item: item["count"], reverse=True)
    if not ranked or ranked[0]["count"] == 0:
        return _t(lang, "Belum ada mention yang menyebut kota administrasi pada periode ini", "No mention names an administrative city in this period")
    top = ranked[0]
    return _t(
        lang,
        f"{top['name']} paling sering disebut, {_num(top['count'])} mention",
        f"{top['name']} is named most often, {_num(top['count'])} mentions",
    )


def _action_title(facts: dict, lang: str) -> str:
    if not facts["advice"]:
        return _t(lang, "Belum ada opsi tindak yang punya bukti pada siklus ini", "No evidenced action is available in this cycle")
    first = facts["advice"][0]
    if first.get("insufficient"):
        return _t(lang, "Opsi teratas belum dapat dijalankan karena bukti belum cukup", "The leading option cannot proceed because the evidence is thin")
    return _t(
        lang,
        f"Opsi teratas berprioritas {first.get('urgency') or GAP} dan memakai {_num(first.get('source_count') or 0)} sumber",
        f"The leading option is priority {first.get('urgency') or GAP} and uses {_num(first.get('source_count') or 0)} sources",
    )


def _clip(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def _t(lang: str, id_text: str, en_text: str) -> str:
    return en_text if lang == "en" else id_text
