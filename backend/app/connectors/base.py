"""Lapisan connector.

Setiap sumber data (berita, media sosial, atau berkas contoh) mengembalikan
daftar `RawItem` yang sama. Pipeline berikutnya tidak perlu tahu asal datanya.

Cara menambah sumber produksi:
1. Buat kelas baru yang mengikuti `SourceConnector`.
2. Daftarkan di `CONNECTORS`.
3. Isi kunci API lewat environment variable, jangan menulis kunci di kode.
4. Jangan melakukan scraping yang melanggar ketentuan platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class RawItem:
    source_name: str
    source_tier: int
    platform: str
    url: str
    author_name: str
    author_handle: str
    published_at: datetime
    title: str
    text: str
    likes: int = 0
    shares: int = 0
    comments: int = 0
    reach_estimate: int = 0
    language: str = "id"
    location: str = ""
    has_public_figure: bool = False
    needs_verification: bool = False
    verification_note: str = ""
    is_kpw: bool = False
    credibility: int = 60
    extra: dict = field(default_factory=dict)


class SourceConnector(Protocol):
    name: str

    def fetch(self, since: datetime) -> list[RawItem]:
        """Ambil konten publik yang terbit setelah `since`."""


class NewsApiConnector:
    """Kerangka NewsAPI / penyedia berita berlisensi. Belum diaktifkan."""

    name = "newsapi"

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError(
            "Sambungkan NEWSAPI_KEY dan lisensi penyedia sebelum mengambil data nyata."
        )


class GdeltConnector:
    """Kerangka GDELT untuk berita global. Belum diaktifkan."""

    name = "gdelt"

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError("Sambungkan konektor GDELT pada tahap integrasi.")


class RssConnector:
    """Kerangka Google News RSS / RSS media. Belum diaktifkan."""

    name = "rss"

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError("Isi daftar URL RSS resmi media, lalu parse feed-nya di sini.")


class OfficialSocialConnector:
    """Kerangka X API, YouTube Data API, atau Meta Graph API. Belum diaktifkan."""

    name = "social-official"

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError(
            "Gunakan API resmi platform. Jangan scrape X, Instagram, TikTok, atau Facebook."
        )
