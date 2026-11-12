"""Berita resmi Pemprov DKI dari portal jakarta.go.id.

Halaman https://www.jakarta.go.id/berita-jakarta mengagregasi tautan
beritajakarta.id (kanal berita resmi Pemprov). Tidak menyimpan HTML penuh —
hanya judul, cuplikan singkat, URL, dan waktu terbit.
"""

from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from urllib.parse import urljoin

from app.connectors.base import RawItem
from app.connectors.http_util import fetch_bytes
from app.services.clock import now_wib
from app.services.urls import canonical_url

LISTING_URLS = (
    "https://www.jakarta.go.id/berita-jakarta",
    "https://www.jakarta.go.id/berita-jakarta?page=2&news=",
)

_ARTICLE_HREF = re.compile(
    r'href=["\'](https?://(?:www\.)?beritajakarta\.id/read/\d+/[^"\']+)["\']',
    re.I,
)
_DATETIME = re.compile(
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)",
)
_TAG = re.compile(r"<[^>]+>")


def fetch_pemprov_official(limit: int = 24) -> list[RawItem]:
    """Ambil daftar berita terkini dari portal resmi Pemprov DKI."""
    seen: set[str] = set()
    items: list[RawItem] = []
    for address in LISTING_URLS:
        if len(items) >= limit:
            break
        try:
            html = fetch_bytes(address, timeout=15, attempts=2).decode("utf-8", "replace")
        except Exception:
            continue
        items.extend(_parse_listing(html, seen, limit - len(items)))
    return items


def _parse_listing(html: str, seen: set[str], limit: int) -> list[RawItem]:
    output: list[RawItem] = []
    for match in _ARTICLE_HREF.finditer(html):
        if len(output) >= limit:
            break
        raw_url = unescape(match.group(1)).split("#")[0]
        url = canonical_url(raw_url) or raw_url
        key = url.casefold()
        if key in seen:
            continue
        seen.add(key)
        window = html[max(0, match.start() - 500) : match.end() + 900]
        title = _nearest_title(window, url)
        if not title:
            continue
        published = _nearest_date(window) or now_wib()
        snippet = _nearest_snippet(window, title)
        output.append(
            RawItem(
                source_name="Portal Pemprov DKI",
                source_tier=1,
                platform="berita",
                url=url,
                author_name="Pemprov DKI Jakarta",
                author_handle="@dkijakarta",
                published_at=published,
                title=title[:300],
                text=(snippet or "Cuplikan dari portal resmi Pemprov DKI Jakarta.")[:360],
                credibility=85,
                location="DKI Jakarta",
            )
        )
    return output


def _nearest_title(window: str, url: str) -> str:
    # Judul sering di <h4>…</h4> atau teks alt/anchor di sekitar tautan.
    for pattern in (
        r"<h4[^>]*>(.*?)</h4>",
        r"<h3[^>]*>(.*?)</h3>",
        r"<a[^>]+href=[\"'][^\"']*beritajakarta\.id/read/[^\"']+[\"'][^>]*>(.*?)</a>",
    ):
        found = re.findall(pattern, window, re.I | re.S)
        for chunk in found:
            title = _clean(chunk)
            if len(title) >= 12 and "beritajakarta" not in title.casefold():
                return title
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[-_]+", " ", slug).strip()
    return slug[:200] if slug else ""


def _nearest_date(window: str) -> datetime | None:
    hit = _DATETIME.search(window)
    if not hit:
        return None
    raw = hit.group(1).replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _nearest_snippet(window: str, title: str) -> str:
    text = _clean(window)
    folded = text.casefold()
    idx = folded.find(title.casefold())
    if idx >= 0:
        text = text[idx + len(title) :]
    text = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:280]


def _clean(value: str) -> str:
    text = unescape(_TAG.sub(" ", value or ""))
    return re.sub(r"\s+", " ", text).strip()
