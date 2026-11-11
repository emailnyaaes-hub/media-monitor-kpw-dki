import unittest

from types import SimpleNamespace

from app.services.matching import eligible_for_ingest, matches_beranda_query


class BerandaIngestTests(unittest.TestCase):
    def test_beranda_without_bi_keyword(self):
        queries = [
            SimpleNamespace(
                name="Paket berita nasional Beranda",
                expression="(Indonesia OR politik OR pemerintah) AND NOT (lowongan OR karir)",
                is_active=True,
            )
        ]
        text = "Presiden tinjau infrastruktur nasional di Jawa Tengah"
        self.assertTrue(matches_beranda_query(text, queries))
        self.assertTrue(eligible_for_ingest(text, [], queries))

    def test_rejects_without_query_or_keyword(self):
        queries = [
            SimpleNamespace(
                name="Paket institusi",
                expression='"Bank Indonesia"',
                is_active=True,
            )
        ]
        text = "Skandal lokal tanpa kata kunci"
        self.assertFalse(eligible_for_ingest(text, [], queries))


if __name__ == "__main__":
    unittest.main()
