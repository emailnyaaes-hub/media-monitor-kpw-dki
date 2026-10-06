from app.connectors.base import (
    GdeltConnector,
    NewsApiConnector,
    OfficialSocialConnector,
    RssConnector,
)
# Pengambilan aktif ada di app.connectors.live. Data contoh tidak dipakai.
ACTIVE_CONNECTORS: list = []

AVAILABLE_CONNECTORS = {
    "newsapi": NewsApiConnector,
    "gdelt": GdeltConnector,
    "rss": RssConnector,
    "social-official": OfficialSocialConnector,
}
