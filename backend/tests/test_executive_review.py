import os
import unittest
from unittest import mock
from datetime import datetime
from types import SimpleNamespace

from app.services.content_review import review
from app.services.executive import _scope, _summary


def row(**extra):
    base = dict(
        location="",
        title="Bank Indonesia menjaga stabilitas rupiah",
        text="Judul media nasional.",
        category="Rupiah/Kurs",
        sentiment="netral",
        published_at=datetime(2026, 10, 21, 9, 0),
        source_name="Detik",
        url="https://finance.detik.com/contoh",
    )
    base.update(extra)
    return SimpleNamespace(**base)


class ExecutiveTests(unittest.TestCase):
    def test_scope_dki_and_other_province(self):
        self.assertEqual(_scope(row(category="Ekonomi Jakarta"))[0], "dki")
        self.assertEqual(_scope(row(title="KPw BI Jawa Barat bahas inflasi daerah", text=""))[1], "Jawa Barat")
        self.assertEqual(_scope(row())[0], "nasional")

    def test_summary_uses_only_given_links(self):
        item = row()
        links = [{"source_name": "Detik", "title": item.title, "url": item.url, "published_at": "2026-10-21"}]
        text = _summary(item.title, [item], "netral", {"positif": 0, "netral": 100, "negatif": 0}, links)
        self.assertGreaterEqual(text.count("."), 5)
        self.assertLessEqual(text.count("."), 10)
        self.assertIn("Detik", text)
        self.assertNotIn("https://example.com", text)


class ReviewTests(unittest.TestCase):
    def test_flags_identity_number_without_invented_pasal(self):
        with mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = review(
                "Bank Indonesia mengingatkan masyarakat. Nomor 3175090909090001 tidak boleh diumumkan pada caption ini.",
                "caption",
                "Instagram",
            )
        self.assertTrue(any(item["risiko"] == "Tinggi" for item in result["findings"]))
        blob = " ".join(item["dasar_hukum"] for item in result["findings"])
        self.assertNotIn("Pasal 5", blob)
        self.assertIn("verifikasi", blob.lower())
        self.assertIn("alat bantu", result["disclaimer"].lower())

    def test_clean_draft_can_be_ready(self):
        with mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            result = review(
                "Bank Indonesia menyampaikan perkembangan sistem pembayaran pada tahun 2026 kepada media.",
                "siaran",
                "",
            )
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["status"], "Siap Terbit")


if __name__ == "__main__":
    unittest.main()
