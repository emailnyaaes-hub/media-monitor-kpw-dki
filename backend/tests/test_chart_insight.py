import json
import os
import unittest
from datetime import date, datetime, time, timedelta
from unittest import mock

from app.services import chart_insight
from test_voice import row

WINDOW = {
    "date_from": date(2026, 10, 1),
    "date_to": date(2026, 10, 10),
    "start": datetime.combine(date(2026, 10, 1), time.min),
    "end": datetime.combine(date(2026, 10, 10), time.max),
    "platform": None,
    "category": None,
    "location": None,
}


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def count(self):
        return len(self.rows)


def patched(current, previous):
    def base_query(_db, window):
        return FakeQuery(current if window["date_from"] == WINDOW["date_from"] else previous)

    return mock.patch.object(chart_insight.analytics, "base_query", side_effect=base_query)


def sample(count, sentiment="negatif", days=10):
    return [
        row(f"Berita {index}", minutes=index * 60 * 24 * days // max(count, 1), sentiment=sentiment, source_name=f"Media {index % 4}", reach_estimate=0)
        for index in range(count)
    ]


class ChartInsightTests(unittest.TestCase):
    def test_number_normalisation(self):
        self.assertEqual(chart_insight._numbers("10 dan 23,30% serta 4.0"), {"10", "23.3", "4"})

    def test_thin_data_is_flagged(self):
        with patched(sample(2), []):
            result = chart_insight.generate(None, WINDOW, "komposisi")
        self.assertTrue(result["insufficient"])
        self.assertIn(chart_insight.THIN, result["so_what"])
        self.assertIn("Tunda rekomendasi", result["now_what"])
        self.assertEqual(result["keyakinan"], "Rendah")

    def test_negative_composition_reads_threshold_and_links(self):
        rows = sample(8) + sample(4, sentiment="positif")
        with patched(rows, sample(10, sentiment="positif")), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "komposisi")
        self.assertFalse(result["insufficient"])
        self.assertIn("66,7%", result["what_happened"])
        self.assertIn("ambang pantau", result["so_what"])
        self.assertIn("klarifikasi", result["now_what"].casefold())
        self.assertTrue(result["evidence"])
        self.assertTrue(all(item["url"].startswith("https://") for item in result["evidence"]))
        self.assertIn("insight-5w1h-1", result["method"])
        self.assertIn("komposisi sentimen", result["what_happened"].casefold())
        self.assertTrue(result["why"])
        self.assertTrue(result["who"])
        self.assertEqual(result["framework"], "5W1H")

    def test_trend_without_previous_period_says_so(self):
        with patched(sample(12), []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "trend")
        self.assertIn("belum bisa dihitung", result["what_happened"])
        self.assertIn("Ringkasan eksekutif", result["what_happened"])
        self.assertIn("Rentang pantauan", result["when"])

    def test_trend_and_kata_voices_differ(self):
        rows = [row(f"Rupiah melemah terhadap dolar {index}", minutes=index * 60, source_name=f"Media {index % 4}", reach_estimate=0) for index in range(8)]
        with patched(rows, []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            trend = chart_insight.generate(None, WINDOW, "trend")
            kata = chart_insight.generate(None, WINDOW, "kata")
        self.assertIn("Ringkasan eksekutif", trend["what_happened"])
        self.assertIn("Isu & tren", kata["what_happened"])
        self.assertNotEqual(trend["what_happened"][:80], kata["what_happened"][:80])
        self.assertIn("judul", trend["why"].casefold())

    def test_top_word_insight_cites_rows_with_that_word(self):
        rows = [row(f"Rupiah melemah terhadap dolar {index}", minutes=index * 60, source_name=f"Media {index % 4}", reach_estimate=0) for index in range(6)]
        with patched(rows, []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "kata")
        self.assertIn("rupiah", result["what_happened"])
        self.assertTrue(all("Rupiah" in item["title"] for item in result["evidence"]))
        self.assertNotEqual(result["keyakinan"], "Tinggi")
        self.assertIn("rupiah", result["why"].casefold())

    def test_voice_insight_flags_hoax_first(self):
        rows = [row(f"Pedagang mengeluh QRIS error saat transaksi {index}", minutes=index * 60, reach_estimate=0) for index in range(4)]
        rows.append(row("Hoaks undian mengatasnamakan Bank Indonesia", minutes=600, reach_estimate=0))
        with patched(rows, []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "suara")
        self.assertIn("Ramai belum bisa dihitung", result["what_happened"])
        self.assertIn("keluhan", result["so_what"])
        self.assertIn("hoaks", result["so_what"])
        self.assertIn("Hoaks", result["evidence"][0]["title"])
        self.assertIn("hoaks", result["why"].casefold() + result["how"].casefold())

    def test_why_without_titles_stays_cautious(self):
        rows = sample(2)
        for item in rows:
            item.title = ""
        with patched(rows, []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "komposisi")
        self.assertIn("jangan menyimpulkan", result["why"].casefold())

    def test_llm_output_with_invented_number_is_rejected(self):
        base = {
            "who": "Media A (12)",
            "what": "Ada 12 mention.",
            "when": "2026-10-01 s.d. 2026-10-10",
            "where": "Lokasi tidak tercatat.",
            "why": "Kategori dominan Inflasi dari data fokus.",
            "how": "Pola naik bertahap.",
            "so": "Perhatian menguat.",
            "now": "Pantau.",
        }
        invented = json.dumps(
            {
                "who": "Media A (12)",
                "what": "Ada 12 mention.",
                "when": "2026-10-01 s.d. 2026-10-10",
                "where": "Lokasi tidak tercatat.",
                "why": "Kategori dominan Inflasi dari data fokus.",
                "how": "Pola naik bertahap.",
                "so_what": "Naik 300%.",
                "now_what": "Pantau.",
            }
        )
        clean = json.dumps(
            {
                "who": "Media A (12)",
                "what": "Ada 12 mention.",
                "when": "2026-10-01 s.d. 2026-10-10",
                "where": "Lokasi tidak tercatat.",
                "why": "Kategori dominan Inflasi dari data fokus.",
                "how": "Pola naik bertahap.",
                "so_what": "Perhatian menguat.",
                "now_what": "Pantau.",
            }
        )
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "x"}):
            with mock.patch.object(chart_insight, "_complete", return_value=invented):
                self.assertIsNone(chart_insight._llm("trend", {"total": 12}, base))
            with mock.patch.object(chart_insight, "_complete", return_value=clean):
                self.assertEqual(chart_insight._llm("trend", {"total": 12}, base)["so"], "Perhatian menguat.")


if __name__ == "__main__":
    unittest.main()
