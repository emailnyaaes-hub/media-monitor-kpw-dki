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

    def test_kpw_dki_keywords_from_catalog(self):
        samples = [
            "Iwan Setiawan tinjau UMKM DKI Jakarta",
            "BI Jakarta gelar Jakarta Economic Forum",
            "TPID Jakarta pantau Inflasi Tahunan DKI Jakarta",
            "Kerak Telor BI Jakarta bersama pelaku usaha",
            "JITEX dan Jakarta Youth Leadership Camp dibuka",
            "Indonesia Sharia Economic Forum (ISEF) di Jakarta",
            "Bank Indonesia pantau inflasi di Jakarta Pusat",
            "Edukasi QRIS untuk UMKM di DKI Jakarta",
            "BI DKI Optimistis Ekonomi Jakarta Tumbuh Lebih Kuat",
            "Ekonomi DKI Jakarta Tumbuh 5,87%, BI Ungkap Pemicunya",
            "BI dan Pemprov DKI Perkuat Sinergi Investasi",
        ]
        for title in samples:
            self.assertEqual(classify_feed_section(row(title=title)), "kpw_dki", title)

    def test_kpw_provinsi_not_dki(self):
        samples = [
            "KPw BI Jawa Barat bahas inflasi daerah",
            "Kantor Perwakilan Bank Indonesia Provinsi Bali gelar edukasi QRIS",
            "KPwBI Sumatera Utara pantau TPID",
            "BI Jawa Timur perkuat UMKM daerah",
            "Kantor Perwakilan Bank Indonesia Provinsi Jawa Barat (KPwBI Jabar) akselerasi ekonomi",
        ]
        for title in samples:
            self.assertEqual(classify_feed_section(row(title=title)), "kpw_provinsi", title)

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
        samples = [
            "Pemprov DKI Jakarta luncurkan Jakarta Smart City",
            "Balai Kota Jakarta gelar operasi Satpol PP",
            "Gubernur DKI Pramono Anung tinjau banjir",
            "Diskominfo Jakarta perbarui Jakartasatu",
        ]
        for title in samples:
            self.assertEqual(classify_feed_section(row(title=title)), "pemprov_dki", title)

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
