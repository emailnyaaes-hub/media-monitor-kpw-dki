"""Connector data contoh.

Isinya meniru bentuk hasil API berita dan media sosial, tetapi tidak
menghubungi internet. Aman dijalankan berulang: item yang sama dilewati
lewat content_hash di pipeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.connectors.base import RawItem
from app.services.clock import now_wib


class MockFeedConnector:
    name = "mock-feed"

    def fetch(self, since: datetime) -> list[RawItem]:
        raise RuntimeError("Data contoh dinonaktifkan. Gunakan sumber RSS atau API resmi.")
        now = now_wib()
        items = [
            RawItem(
                source_name="Detik",
                source_tier=1,
                platform="berita",
                url="https://contoh.media-monitor.local/berita/hoaks-varian-rekrutmen",
                author_name="Redaksi Detik",
                author_handle="detikcom",
                published_at=now - timedelta(minutes=25),
                title="Beredar varian baru hoaks rekrutmen pegawai mengatasnamakan Bank Indonesia",
                text=(
                    "Warga kembali membagikan tautan rekrutmen fiktif yang memakai nama Bank Indonesia. "
                    "Kanal resmi mengingatkan masyarakat agar tidak mengisi data pribadi pada formulir "
                    "yang tidak terverifikasi. Isu hoaks ini berisiko menipu pelamar kerja."
                ),
                likes=420,
                shares=860,
                comments=190,
                reach_estimate=240000,
                has_public_figure=False,
                credibility=88,
            ),
            RawItem(
                source_name="Instagram",
                source_tier=1,
                platform="instagram",
                url="https://contoh.media-monitor.local/ig/kpw-edukasi-qris",
                author_name="KPw BI DKI Jakarta",
                author_handle="@kpwbi_dki",
                published_at=now - timedelta(minutes=50),
                title="Edukasi QRIS untuk pelaku UMKM di Pasar Mayestik",
                text=(
                    "KPw BI DKI Jakarta menggelar edukasi QRIS bagi pedagang Pasar Mayestik. "
                    "Peserta menyebut pembayaran menjadi lebih mudah dan tercatat. "
                    "Kegiatan ini bagian dari literasi sistem pembayaran di Jakarta Selatan."
                ),
                likes=980,
                shares=140,
                comments=76,
                reach_estimate=42000,
                location="Jakarta Selatan",
                is_kpw=True,
                credibility=90,
            ),
            RawItem(
                source_name="X",
                source_tier=3,
                platform="x",
                url="https://contoh.media-monitor.local/x/rupiah-pagi",
                author_name="Analis Pasar",
                author_handle="@ekonomi_terbuka",
                published_at=now - timedelta(minutes=12),
                title="Rupiah pagi ini masih di bawah tekanan dolar",
                text=(
                    "Rupiah masih melemah di tengah penguatan dolar. Pasar menunggu arahan "
                    "nilai tukar dan komunikasi Bank Indonesia agar volatilitas tidak melebar. #Rupiah"
                ),
                likes=210,
                shares=90,
                comments=40,
                reach_estimate=56000,
                has_public_figure=False,
                credibility=55,
            ),
        ]
        return [item for item in items if item.published_at >= since]
