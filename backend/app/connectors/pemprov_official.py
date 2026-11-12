"""Berita resmi Pemprov DKI dari portal jakarta.go.id + beritajakarta.id.

Halaman https://www.jakarta.go.id/berita-jakarta mengagregasi tautan
beritajakarta.id (kanal berita resmi Pemprov). Fallback: beranda beritajakarta.id.
Tidak menyimpan HTML penuh — hanya judul, cuplikan singkat, URL, dan waktu terbit.

Versi fetcher: pemprov-official-v2
"""

from __future__ import annotations

import re
from datetime import datetime
from html import unescape

from app.connectors.base import RawItem
from app.connectors.http_util import fetch_bytes
from app.services.clock import now_wib
from app.services.urls import canonical_url

LISTING_URLS = (
    "https://www.beritajakarta.id/",
    "https://m.beritajakarta.id/",
    "https://www.jakarta.go.id/berita-jakarta",
)

_ARTICLE_HREF = re.compile(
    r"""href=["'](
        https?://(?:www\.|m\.)?beritajakarta\.id/read/\d+/[^"'#?\s]+
        | /read/\d+/[^"'#?\s]+
    )["']""",
    re.I | re.X,
)
_DATETIME = re.compile(
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)",
)
_TAG = re.compile(r"<[^>]+>")


def fetch_pemprov_official(limit: int = 24) -> list[RawItem]:
    """Ambil daftar berita terkini dari portal resmi Pemprov DKI / BeritaJakarta."""
    seen: set[str] = set()
    items: list[RawItem] = []
    errors: list[str] = []
    for address in LISTING_URLS:
        if len(items) >= limit:
            break
        try:
            # Timeout ketat: di Vercel jangan sampai menahan seluruh Perbarui.
            html = fetch_bytes(address, timeout=8, attempts=1).decode("utf-8", "replace")
        except Exception as exc:
            errors.append(f"{address}:{exc.__class__.__name__}")
            continue
        batch = _parse_listing(html, seen, limit - len(items), base=address)
        items.extend(batch)
    # Simpan jejak error di objek kosong lewat attribute dinamis tidak perlu —
    # caller cukup cek len(items).
    if not items and errors:
        raise RuntimeError("; ".join(errors[:3]))
    return items


def _parse_listing(html: str, seen: set[str], limit: int, base: str) -> list[RawItem]:
    output: list[RawItem] = []
    for match in _ARTICLE_HREF.finditer(html):
        if len(output) >= limit:
            break
        raw = unescape(match.group(1)).split("#")[0].split("?")[0]
        if raw.startswith("/"):
            raw = "https://www.beritajakarta.id" + raw
        raw = raw.replace("://m.beritajakarta.id", "://www.beritajakarta.id")
        url = canonical_url(raw) or raw
        key = url.casefold()
        if key in seen:
            continue
        seen.add(key)
        window = html[max(0, match.start() - 600) : match.end() + 1000]
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
    for pattern in (
        r"<h4[^>]*>(.*?)</h4>",
        r"<h3[^>]*>(.*?)</h3>",
        r"<h2[^>]*>(.*?)</h2>",
        r"<a[^>]+href=[\"'][^\"']*/read/\d+/[^\"']+[\"'][^>]*>(.*?)</a>",
        r'alt=["\']([^"\']{12,200})["\']',
    ):
        found = re.findall(pattern, window, re.I | re.S)
        for chunk in found:
            title = _clean(chunk)
            if len(title) >= 12 and "beritajakarta" not in title.casefold() and "jakarta.go.id" not in title.casefold():
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
