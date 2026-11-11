import unittest
from datetime import datetime

from app.models import Mention
from app.services.mention_brief import build_mention_brief, mention_brief_for_row


def _row(**extra):
    base = dict(
        content_hash="abc",
        source_name="Detik",
        source_tier=1,
        platform="berita",
        url="https://example.com/a",
        author_name="Redaksi",
        author_handle="",
        published_at=datetime(2026, 11, 1, 9, 0),
        title="Bank Indonesia tegaskan stabilitas rupiah",
        text="Gubernur BI menyampaikan bahwa intervensi valuta asing tetap terukur pada Oktober 2026.",
        sentiment="netral",
        stance="netral",
        category="Rupiah/Kurs",
        needs_verification=False,
        quotes_bi=True,
        is_kpw=False,
        brief="",
    )
    base.update(extra)
    return Mention(**base)


class MentionBriefTests(unittest.TestCase):
    def test_three_sentences_with_snippet(self):
        brief = build_mention_brief(_row())
        self.assertGreaterEqual(brief.count("."), 2)
        self.assertIn("Rupiah/Kurs", brief)
        self.assertIn("Bank Indonesia", brief)

    def test_hoaks_adds_verification_line(self):
        brief = build_mention_brief(_row(category="Hoaks/Penipuan", needs_verification=True))
        self.assertIn("verifikasi", brief.lower())

    def test_prefers_stored_brief(self):
        row = _row(brief="Ringkasan tersimpan.")
        self.assertEqual(mention_brief_for_row(row), "Ringkasan tersimpan.")

    def test_placeholder_snippet_uses_title_path(self):
        brief = build_mention_brief(_row(text="Cuplikan tidak tersedia di feed. Buka sumber asli."))
        self.assertIn("berjudul", brief)


if __name__ == "__main__":
    unittest.main()
