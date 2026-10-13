import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.nlp.voice import build_brief, describe_mention, lexical_voices, solution_table, tools_map


def row(title, text="", minutes=0, **extra):
    base = dict(
        id=minutes + 1,
        title=title,
        text=text,
        url=f"https://contoh-media.id/berita/{minutes}",
        source_name=extra.pop("source_name", f"Media {minutes % 3}"),
        source_tier=2,
        platform="berita",
        category="Sistem Pembayaran",
        sentiment="negatif",
        stance="downside",
        published_at=datetime(2026, 10, 1, 8) + timedelta(minutes=minutes),
        location="",
        policy_tags="[]",
        policy_relevance=0,
        risk_score=40,
        spread_velocity=20,
        credibility=70,
        has_public_figure=False,
        is_kpw=False,
        issue_id=None,
        voice_override="",
        segment_override="",
    )
    base.update(extra)
    return SimpleNamespace(**base)


class VoiceTests(unittest.TestCase):
    def test_complaint_and_hoax(self):
        self.assertIn("keluhan", lexical_voices(row("Pedagang mengeluh QRIS error saat transaksi")))
        self.assertIn("hoaks", lexical_voices(row("Hoaks undian mengatasnamakan Bank Indonesia")))

    def test_unknown_area_is_not_guessed(self):
        info = describe_mention(row("QRIS gangguan di pasar"))
        self.assertEqual(info["area"], "wilayah tidak diketahui")

    def test_analyst_override_wins(self):
        info = describe_mention(row("QRIS error", voice_override='["apresiasi"]'))
        self.assertEqual(info["voices"], ["apresiasi"])

    def test_brief_labels_hypothesis_and_links_sources(self):
        rows = [row("QRIS error dan transaksi gagal", minutes=i * 30) for i in range(5)]
        brief = build_brief(rows)
        self.assertTrue(all(item["label"] == "Hipotesis AI" for item in brief["kenapa"]["hipotesis"]))
        self.assertTrue(all(item["url"].startswith("https://") for item in brief["bukti"]))
        self.assertEqual(len(brief["dampak"]), 4)

    def test_thin_data_is_flagged(self):
        brief = build_brief([row("QRIS error", minutes=0)])
        self.assertEqual(brief["rekomendasi"]["teks"], "Data belum cukup, perlu verifikasi")

    def test_ramai_needs_previous_period(self):
        from app.nlp.voice import snapshot

        rows = [row("QRIS lancar", minutes=i) for i in range(5)]
        data = snapshot(rows, [])
        self.assertEqual(data["topik_ramai"], [])
        self.assertFalse(data["ramai_tersedia"])

    def test_plenty_of_data_without_pattern_is_not_called_thin(self):
        rows = [row("Rapat membahas ekonomi", minutes=i, source_name=f"Media {i}", sentiment="netral") for i in range(6)]
        brief = build_brief(rows)
        self.assertNotEqual(brief["rekomendasi"]["teks"], "Data belum cukup, perlu verifikasi")
        self.assertFalse(brief["rekomendasi"]["insufficient"])

    def test_price_needs_other_parties(self):
        rows = [row("Warga mengeluh harga cabai mahal", minutes=i, category="Inflasi") for i in range(3)]
        items = solution_table(rows)
        self.assertTrue(any(item["luar_kewenangan"] for item in items))

    def test_gap_matrix_marks_verification(self):
        allowed = {"Terverifikasi publik", "Perlu konfirmasi internal", "Asumsi"}
        data = tools_map()
        self.assertTrue(all(item["status"] in allowed for item in data["matriks"]))
        self.assertTrue(10 <= len(data["pertanyaan"]) <= 15)


if __name__ == "__main__":
    unittest.main()
