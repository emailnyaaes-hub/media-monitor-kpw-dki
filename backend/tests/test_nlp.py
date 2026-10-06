import unittest

from app.nlp import analyze
from app.nlp.boolean import ExpressionError, match_expression
from app.nlp.risk import score_risk


class ClassifierTests(unittest.TestCase):
    def test_hoax_is_downside(self):
        result = analyze("Beredar hoaks undian berhadiah mengatasnamakan Bank Indonesia, jangan sampai tertipu")
        self.assertEqual(result["stance"], "downside")
        self.assertEqual(result["category"], "Hoaks/Penipuan")

    def test_qris_is_upside(self):
        result = analyze("QRIS memudahkan UMKM Jakarta, transaksi jadi lebih cepat dan aman serta lancar")
        self.assertEqual(result["stance"], "upside")

    def test_slang_negative(self):
        result = analyze("rupiah nyungsep bgt hari ini, gak stabil, melemah terus")
        self.assertEqual(result["sentiment"], "negatif")

    def test_negation_is_not_hoax(self):
        result = analyze("Ini bukan hoaks, klarifikasi resmi Bank Indonesia sudah tayang dan aman")
        self.assertNotEqual(result["sentiment"], "negatif")

    def test_sarcasm(self):
        result = analyze("makasih ya BI, BI-FAST-nya mantap sekali anjlok dan transfer gagal")
        self.assertEqual(result["sentiment"], "negatif")

    def test_downside_risk_higher_than_upside(self):
        negative = score_risk(
            sentiment="negatif", stance="downside", reach=500000,
            source_tier=1, velocity=80, has_public_figure=True, credibility=90,
        )
        positive = score_risk(
            sentiment="positif", stance="upside", reach=500000,
            source_tier=1, velocity=80, has_public_figure=True, credibility=90,
        )
        self.assertGreater(negative, positive)
        self.assertLessEqual(negative, 100)


class BooleanTests(unittest.TestCase):
    def test_and_not(self):
        expr = '"Bank Indonesia" AND NOT lowongan'
        self.assertTrue(match_expression(expr, "Bank Indonesia rilis laporan"))
        self.assertFalse(match_expression(expr, "lowongan Bank Indonesia dibuka"))

    def test_or_group(self):
        expr = 'QRIS OR "BI-FAST"'
        self.assertTrue(match_expression(expr, "Gangguan BI-FAST singkat"))
        self.assertFalse(match_expression(expr, "hanya membahas inflasi pangan"))

    def test_bad_expression(self):
        with self.assertRaises(ExpressionError):
            match_expression("AND QRIS", "QRIS")


if __name__ == "__main__":
    unittest.main()
