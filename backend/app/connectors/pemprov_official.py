"""Berita resmi Pemprov DKI dari portal jakarta.go.id + beritajakarta.id.

Halaman https://www.jakarta.go.id/berita-jakarta mengagregasi tautan
beritajakarta.id (kanal berita resmi Pemprov). Fallback: beranda beritajakarta.id.
Tidak menyimpan HTML penuh — hanya judul, cuplikan singkat, URL, dan waktu terbit.

Versi fetcher: pemprov-official-v3b
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import unescape

from app.connectors.base import RawItem
from app.connectors.http_util import fetch_bytes
from app.services.clock import now_wib
from app.services.urls import canonical_url

# Satu URL utama dulu (cepat); sisanya pelengkap bila masih kurang.
LISTING_URLS = (
    "https://www.beritajakarta.id/",
    "https://www.jakarta.go.id/berita-jakarta",
    "https://m.beritajakarta.id/",
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

    def _one(address: str) -> tuple[str, bytes | None, str | None]:
        try:
            # Timeout ketat: di Vercel egress ke portal sering lambat/diblok.
            return address, fetch_bytes(address, timeout=4, attempts=1), None
        except Exception as exc:
            return address, None, f"{address}:{exc.__class__.__name__}"

    # Parallel agar 3× timeout tidak menjumlah jadi 12s; shutdown tanpa menunggu.
    from concurrent.futures import TimeoutError as FuturesTimeout

    pool = ThreadPoolExecutor(max_workers=3)
    try:
        futures = [pool.submit(_one, address) for address in LISTING_URLS]
        for future in as_completed(futures, timeout=6):
            address, payload, err = future.result(timeout=0.1)
            if err:
                errors.append(err)
                continue
            if not payload or len(items) >= limit:
                continue
            html = payload.decode("utf-8", "replace")
            batch = _parse_listing(html, seen, limit - len(items), base=address)
            items.extend(batch)
    except (TimeoutError, FuturesTimeout):
        pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

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
        window = html[max(0, match.start() - 400) : match.end() + 800]
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
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug_title = re.sub(r"[-_]+", " ", slug).strip()
    for pattern in (
        r"<h4[^>]*>(.*?)</h4>",
        r"<h3[^>]*>(.*?)</h3>",
        r"<h2[^>]*>(.*?)</h2>",
        r"<a[^>]+href=[\"'][^\"']*/read/\d+/[^\"']+[\"'][^>]*>(.*?)</a>",
        r'alt=["\']([^"\']{12,200})["\']',
        r'title=["\']([^"\']{12,200})["\']',
    ):
        found = re.findall(pattern, window, re.I | re.S)
        for chunk in found:
            title = _clean(chunk)
            if len(title) < 12:
                continue
            folded = title.casefold()
            if "beritajakarta" in folded or "jakarta.go.id" in folded:
                continue
            # Tolak judul dari kartu tetangga bila slug URL jelas berbeda.
            if slug_title and len(slug_title) >= 12:
                slug_tokens = {t for t in slug_title.casefold().split() if len(t) > 3}
                title_tokens = {t for t in folded.split() if len(t) > 3}
                if slug_tokens and title_tokens and len(slug_tokens & title_tokens) == 0:
                    continue
            return title
    return slug_title[:200] if slug_title else ""


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
