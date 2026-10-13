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
        self.assertEqual(result["so_what"], chart_insight.THIN)
        self.assertEqual(result["now_what"], chart_insight.THIN)
        self.assertEqual(result["keyakinan"], "Rendah")

    def test_negative_composition_reads_threshold_and_links(self):
        rows = sample(8) + sample(4, sentiment="positif")
        with patched(rows, sample(10, sentiment="positif")), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "komposisi")
        self.assertFalse(result["insufficient"])
        self.assertIn("66,7%", result["what_happened"])
        self.assertIn("ambang pantau", result["so_what"])
        self.assertIn("pimpinan", result["now_what"])
        self.assertTrue(result["evidence"])
        self.assertTrue(all(item["url"].startswith("https://") for item in result["evidence"]))
        self.assertEqual(result["method"], "Aturan dari data grafik")

    def test_trend_without_previous_period_says_so(self):
        with patched(sample(12), []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "trend")
        self.assertIn("belum bisa dihitung", result["what_happened"])

    def test_top_word_insight_cites_rows_with_that_word(self):
        rows = [row(f"Rupiah melemah terhadap dolar {index}", minutes=index * 60, source_name=f"Media {index % 4}", reach_estimate=0) for index in range(6)]
        with patched(rows, []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "kata")
        self.assertIn("rupiah", result["what_happened"])
        self.assertTrue(all("Rupiah" in item["title"] for item in result["evidence"]))
        self.assertNotEqual(result["keyakinan"], "Tinggi")

    def test_voice_insight_flags_hoax_first(self):
        rows = [row(f"Pedagang mengeluh QRIS error saat transaksi {index}", minutes=index * 60, reach_estimate=0) for index in range(4)]
        rows.append(row("Hoaks undian mengatasnamakan Bank Indonesia", minutes=600, reach_estimate=0))
        with patched(rows, []), mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = chart_insight.generate(None, WINDOW, "suara")
        self.assertIn("Ramai belum bisa dihitung", result["what_happened"])
        self.assertIn("keluhan", result["so_what"])
        self.assertIn("hoaks", result["so_what"])
        self.assertIn("Hoaks", result["evidence"][0]["title"])

    def test_llm_output_with_invented_number_is_rejected(self):
        base = {"what": "Ada 12 mention."}
        invented = '{"what_happened": "Ada 12 mention.", "so_what": "Naik 300%.", "now_what": "Pantau."}'
        clean = '{"what_happened": "Ada 12 mention.", "so_what": "Perhatian menguat.", "now_what": "Pantau."}'
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "x"}):
            with mock.patch.object(chart_insight, "_complete", return_value=invented):
                self.assertIsNone(chart_insight._llm("trend", {"total": 12}, base))
            with mock.patch.object(chart_insight, "_complete", return_value=clean):
                self.assertEqual(chart_insight._llm("trend", {"total": 12}, base)["so"], "Perhatian menguat.")


if __name__ == "__main__":
    unittest.main()
