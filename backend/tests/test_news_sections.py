import unittest
from datetime import datetime

from app.models import Mention
from app.services.news_sections import classify_feed_section


def row(**extra):
    base = dict(
        content_hash="x",
        source_name="Detik",
        source_tier=1,
        platform="berita",
        url="https://example.com/1",
        author_name="Redaksi",
        author_handle="",
        published_at=datetime(2026, 11, 1),
        title="Judul",
        text="Cuplikan.",
        sentiment="netral",
        stance="netral",
        category="Lainnya",
        quotes_bi=False,
        feed_section="beranda",
        brief="",
    )
    base.update(extra)
    return Mention(**base)


class NewsSectionTests(unittest.TestCase):
    def test_kpw_dki(self):
        self.assertEqual(
            classify_feed_section(row(title="KPw BI DKI Jakarta edukasi QRIS", category="Kegiatan KPw DKI")),
            "kpw_dki",
        )

    def test_kpw_provinsi_not_dki(self):
        self.assertEqual(
            classify_feed_section(row(title="KPw BI Jawa Barat bahas inflasi daerah")),
            "kpw_provinsi",
        )

    def test_other_kpw_excludes_dki_only_story(self):
        self.assertEqual(
            classify_feed_section(row(title="KPw BI DKI Jakarta edukasi UMKM")),
            "kpw_dki",
        )
        self.assertNotEqual(
            classify_feed_section(row(title="KPw BI Jawa Barat paparkan inflasi daerah")),
            "kpw_dki",
        )

    def test_pemprov_dki(self):
        self.assertEqual(
            classify_feed_section(row(title="Pemprov DKI Jakarta luncurkan Jakarta Smart City")),
            "pemprov_dki",
        )

    def test_bi_nasional(self):
        self.assertEqual(
            classify_feed_section(row(title="BI pertahankan BI-Rate", category="Kebijakan Moneter")),
            "bi_nasional",
        )

    def test_beranda_only_general(self):
        self.assertEqual(
            classify_feed_section(row(title="Pemerintah evaluasi infrastruktur nasional", text="Cuplikan umum.")),
            "beranda",
        )


if __name__ == "__main__":
    unittest.main()
