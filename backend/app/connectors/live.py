"""Daftar sumber nyata dan statusnya.

RSS yang gagal tidak diganti artikel karangan. Media sosial tanpa kunci API
dilaporkan sebagai tidak tersedia.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import quote, urlsplit

from app.connectors.base import RawItem
from app.connectors.google_decode import publisher_url
from app.connectors.http_util import fetch_bytes
from app.connectors.rss_reader import parse_date, read_atom, read_rss, strip_snippet
from app.services.clock import now_wib
from app.services.urls import canonical_url

# Feed resmi yang pada pemeriksaan terakhir mengembalikan URL artikel penerbit.
DIRECT_FEEDS = [
    ("Detik", 1, "https://finance.detik.com/rss"),
    ("Antara", 1, "https://www.antaranews.com/rss/ekonomi.xml"),
    ("CNN Indonesia", 1, "https://www.cnnindonesia.com/ekonomi/rss"),
    ("Tempo", 1, "https://rss.tempo.co/nasional"),
    ("Liputan6", 2, "https://feed.liputan6.com/rss/bisnis"),
    ("Bloomberg Technoz", 1, "https://www.bloombergtechnoz.com/rss"),
]

# RSS langsung media ini tidak tersedia. Fallback-nya pencarian Google News,
# dan yang disimpan hanya URL penerbit yang berhasil diurai.
GOOGLE_SITE_FEEDS = [
    ("Kompas", "kompas.com"),
    ("CNBC Indonesia", "cnbcindonesia.com"),
    ("Kontan", "kontan.co.id"),
    ("Bisnis.com", "bisnis.com"),
    ("Berita Jakarta", "beritajakarta.id"),
    ("Warta Kota", "wartakota.tribunnews.com"),
]

GOOGLE_QUERIES = [
    '"Bank Indonesia"',
    '"BI-Rate" OR "suku bunga acuan"',
    'QRIS "Bank Indonesia"',
    '"BI-FAST"',
    '"KPw BI" OR "Bank Indonesia Jakarta"',
]


@dataclass
class FetchReport:
    name: str
    status: str
    message: str
    items: list[RawItem] = field(default_factory=list)


def collect_reports(since: datetime, rules: list | None = None) -> list[FetchReport]:
    global _active_rules
    _active_rules = list(rules or [])
    try:
        reports = [fetch_direct(name, tier, url, since) for name, tier, url in DIRECT_FEEDS]
        reports.append(fetch_google_news(since))
        reports.extend(fetch_google_site(name, domain, since) for name, domain in GOOGLE_SITE_FEEDS)
        reports.append(fetch_gdelt(since))
        reports.append(fetch_newsapi(since))
        reports.append(fetch_youtube(since))
        reports.extend(fetch_social(since))
        reports.extend(unavailable_social())
        return reports
    finally:
        _active_rules = []


_active_rules: list = []


def _exclude_owned_sites(query: str) -> str:
    extra = [
        f"-site:{rule.value.strip()}"
        for rule in _active_rules
        if rule.kind == "domain" and rule.is_active and rule.value.strip()
    ]
    if not extra:
        return query
    return f"{query} {' '.join(extra)}"


def _owned(item: RawItem) -> bool:
    from app.services.blocklist import is_blocked

    return is_blocked(item.url, item.author_handle, item.author_name, item.source_name, item.title, _active_rules)


RELEVANT = (
    "bank indonesia",
    "bi-rate",
    "bi-fast",
    "qris",
    "rupiah",
    "kpw bi",
    "suku bunga acuan",
)


def fetch_direct(name: str, tier: int, url: str, since: datetime) -> FetchReport:
    try:
        items = [item for item in read_rss(url, name, tier) if item.published_at >= since and _relevant(item)]
    except Exception as exc:
        return FetchReport(name, "gagal", f"Sumber tidak tersedia. RSS gagal: {exc.__class__.__name__}: {exc}")
    kept = [item for item in items if not _owned(item)][:12]
    if not kept:
        return FetchReport(name, "berhasil", "Feed terbaca. Tidak ada item baru pada jendela waktu ini.", [])
    return FetchReport(name, "berhasil", f"Feed RSS terbaca, {len(kept)} item pada jendela waktu.", kept)


def _relevant(item: RawItem) -> bool:
    hay = f"{item.title}\n{item.text}".casefold()
    return any(term in hay for term in RELEVANT)


def fetch_google_news(since: datetime) -> FetchReport:
    items: list[RawItem] = []
    errors = 0
    for query in GOOGLE_QUERIES:
        try:
            batch, failed = _google_query(query, since, limit=4)
            items.extend(batch)
            errors += failed
            time.sleep(0.3)
        except Exception:
            errors += 1
    if not items and errors:
        return FetchReport("Google News RSS", "gagal", "Sumber tidak tersedia. Pencarian Google News gagal diurai ke URL penerbit.")
    return FetchReport(
        "Google News RSS",
        "berhasil",
        f"{len(items)} tautan penerbit berhasil diurai. {errors} tautan Google News tidak dipakai karena URL penerbitnya tidak didapat.",
        items,
    )


def fetch_google_site(name: str, domain: str, since: datetime) -> FetchReport:
    try:
        items, failed = _google_query(f'"Bank Indonesia" site:{domain}', since, limit=4)
    except Exception as exc:
        return FetchReport(
            f"Google News {name}",
            "gagal",
            f"Sumber tidak tersedia. RSS langsung {name} tidak dipakai, dan pencarian Google News gagal: {exc.__class__.__name__}.",
        )
    if not items:
        return FetchReport(
            f"Google News {name}",
            "gagal" if failed else "berhasil",
            "Sumber tidak tersedia. Tidak ada URL penerbit yang berhasil diurai."
            if failed
            else "Pencarian tidak menemukan item baru.",
        )
    return FetchReport(
        f"Google News {name}",
        "berhasil",
        f"RSS langsung tidak dipakai. {len(items)} artikel {name} didapat dari Google News setelah URL penerbit diurai.",
        items,
    )


def _google_query(query: str, since: datetime, limit: int) -> tuple[list[RawItem], int]:
    address = (
        "https://news.google.com/rss/search?q="
        + quote(f"{_exclude_owned_sites(query)} when:14d")
        + "&hl=id&gl=ID&ceid=ID:id"
    )
    raw_items = read_rss(address, "Google News", 2)
    kept: list[RawItem] = []
    failed = 0
    for item in raw_items:
        if item.published_at < since:
            continue
        if len(kept) >= limit:
            break
        try:
            decoded = canonical_url(publisher_url(item.url))
        except Exception:
            failed += 1
            continue
        if not decoded or "news.google.com" in decoded:
            failed += 1
            continue
        source = _host_label(decoded)
        item.url = decoded
        item.source_name = source
        item.author_name = source
        item.source_tier = 1 if source in {
            "Detik", "Kompas", "CNBC Indonesia", "Kontan", "Bisnis.com",
            "Bloomberg Technoz", "CNN Indonesia", "Tempo", "Antara",
        } else 2
        if _owned(item):
            continue
        kept.append(item)
        time.sleep(0.25)
    return kept, failed


def fetch_gdelt(since: datetime) -> FetchReport:
    query = quote('"Bank Indonesia"')
    address = (
        "https://api.gdeltproject.org/api/v2/doc/doc?query="
        f"{query}&mode=ArtList&maxrecords=15&format=json&sort=DateDesc"
    )
    try:
        payload = json.loads(fetch_bytes(address, attempts=2).decode("utf-8", "replace"))
    except Exception as exc:
        return FetchReport("GDELT", "gagal", f"Sumber tidak tersedia. GDELT menolak atau gagal: {exc.__class__.__name__}: {exc}")
    items: list[RawItem] = []
    for article in payload.get("articles") or []:
        url = canonical_url(article.get("url") or "")
        title = strip_snippet(article.get("title") or "", 240)
        published = _gdelt_date(article.get("seendate"))
        if not url or not title or published is None or published < since:
            continue
        items.append(
            RawItem(
                source_name=article.get("domain") or "GDELT",
                source_tier=2,
                platform="berita",
                url=url,
                author_name=article.get("domain") or "GDELT",
                author_handle="",
                published_at=published,
                title=title,
                text="Cuplikan tidak disertakan GDELT. Buka sumber asli.",
                reach_estimate=0,
                credibility=60,
            )
        )
    return FetchReport("GDELT", "berhasil", f"{len(items)} artikel dari API dokumen GDELT.", items)


def fetch_newsapi(since: datetime) -> FetchReport:
    key = os.environ.get("NEWSAPI_KEY", "").strip()
    if not key:
        return FetchReport(
            "NewsAPI",
            "tidak_tersedia",
            "Sumber tidak tersedia. Butuh NEWSAPI_KEY. Paket gratis NewsAPI terbatas; paket produksi berbayar.",
        )
    address = (
        "https://newsapi.org/v2/everything?q="
        + quote("Bank Indonesia")
        + "&language=id&sortBy=publishedAt&pageSize=20&apiKey="
        + quote(key)
    )
    try:
        payload = json.loads(fetch_bytes(address).decode("utf-8", "replace"))
    except Exception as exc:
        return FetchReport("NewsAPI", "gagal", f"Sumber tidak tersedia. NewsAPI gagal: {exc}")
    if payload.get("status") != "ok":
        return FetchReport("NewsAPI", "gagal", f"Sumber tidak tersedia. NewsAPI: {payload.get('message', 'ditolak')}")
    items = []
    for article in payload.get("articles") or []:
        url = canonical_url(article.get("url") or "")
        title = strip_snippet(article.get("title") or "", 240)
        published = parse_date(article.get("publishedAt"))
        if not url or not title or published is None or published < since:
            continue
        items.append(
            RawItem(
                source_name=(article.get("source") or {}).get("name") or "NewsAPI",
                source_tier=2,
                platform="berita",
                url=url,
                author_name=article.get("author") or (article.get("source") or {}).get("name") or "",
                author_handle="",
                published_at=published,
                title=title,
                text=strip_snippet(article.get("description") or "") or "Cuplikan tidak tersedia. Buka sumber asli.",
                reach_estimate=0,
            )
        )
    return FetchReport("NewsAPI", "berhasil", f"{len(items)} artikel.", items)


# Kanal YouTube resmi BI tidak diambil. Video pihak lain tentang BI tetap lewat Google News.
YOUTUBE_CHANNELS: list[tuple[str, str, str]] = []


def fetch_youtube(since: datetime) -> FetchReport:
    items: list[RawItem] = []
    errors: list[str] = []
    for channel_id, _name, handle in YOUTUBE_CHANNELS:
        address = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            items.extend(read_atom(address, source_tier=1, platform="youtube", handle=handle))
        except Exception as exc:
            errors.append(f"{handle}: {exc.__class__.__name__}")
    wide = min(since, now_wib() - timedelta(days=14))
    try:
        found, failed = _google_query('"Bank Indonesia" site:youtube.com', wide, limit=5)
    except Exception as exc:
        found, failed = [], 1
        errors.append(f"Google News YouTube: {exc.__class__.__name__}")
    else:
        if failed:
            errors.append(f"{failed} tautan YouTube dari Google News tidak terurai.")
    for item in found:
        if "youtube.com" not in item.url and "youtu.be" not in item.url:
            continue
        item.platform = "youtube"
        item.source_tier = 2
        if (item.author_name or "").strip().casefold().lstrip("@") in {"", "youtube", "youtube.com"}:
            from app.services.blocklist import lookup_author

            found = lookup_author(item.url)
            if found:
                item.author_name = found
                item.author_handle = found
                item.source_name = found
        if _owned(item):
            continue
        items.append(item)
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    api_note = ""
    if key:
        searched, api_note = _youtube_api(key, wide)
        items.extend(searched)
    else:
        api_note = "Pencarian seluruh YouTube butuh YOUTUBE_API_KEY. Kanal resmi Bank Indonesia tidak diambil."
    items = [item for item in items if not _owned(item)]
    if not items and errors:
        return FetchReport("YouTube", "gagal", "Sumber tidak tersedia. Feed YouTube gagal: " + "; ".join(errors))
    message = f"{len(items)} video YouTube dari pihak luar Bank Indonesia. {api_note}"
    return FetchReport("YouTube", "berhasil", message.strip(), items)


def _youtube_api(key: str, since: datetime) -> tuple[list[RawItem], str]:
    address = (
        "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=10&q="
        + quote("Bank Indonesia")
        + "&key="
        + quote(key)
        + "&order=date"
    )
    try:
        payload = json.loads(fetch_bytes(address).decode("utf-8", "replace"))
    except Exception as exc:
        return [], f"YouTube Data API gagal: {exc.__class__.__name__}."
    items = []
    for entry in payload.get("items") or []:
        video_id = (entry.get("id") or {}).get("videoId")
        snippet = entry.get("snippet") or {}
        published = parse_date(snippet.get("publishedAt"))
        title = strip_snippet(snippet.get("title") or "", 240)
        if not video_id or not title or published is None or published < since:
            continue
        items.append(
            RawItem(
                source_name=snippet.get("channelTitle") or "YouTube",
                source_tier=2,
                platform="youtube",
                url=f"https://www.youtube.com/watch?v={video_id}",
                author_name=snippet.get("channelTitle") or "YouTube",
                author_handle=snippet.get("channelTitle") or "",
                published_at=published,
                title=title,
                text=strip_snippet(snippet.get("description") or "") or "Cuplikan tidak tersedia. Buka sumber asli.",
                reach_estimate=0,
            )
        )
    return items, f"YouTube Data API menambah {len(items)} video."


def unavailable_social() -> list[FetchReport]:
    return [
        FetchReport(
            "Threads API",
            "tidak_tersedia",
            "Sumber tidak tersedia. Threads tidak punya feed publik. Butuh aplikasi Meta yang disetujui.",
        )
    ]


SOCIAL_QUERIES = [
    ("Instagram", "instagram", ("instagram.com",), '"Bank Indonesia" site:instagram.com'),
    ("TikTok", "tiktok", ("tiktok.com",), '"Bank Indonesia" site:tiktok.com'),
    ("X", "x", ("x.com", "twitter.com"), '"Bank Indonesia" (site:x.com OR site:twitter.com)'),
    ("Facebook", "facebook", ("facebook.com",), '"Bank Indonesia" site:facebook.com'),
]

def fetch_social(since: datetime) -> list[FetchReport]:
    wide = min(since, now_wib() - timedelta(days=14))
    return [_fetch_social_one(name, platform, hosts, query, wide) for name, platform, hosts, query in SOCIAL_QUERIES]


def _fetch_social_one(name: str, platform: str, hosts: tuple[str, ...], query: str, since: datetime) -> FetchReport:
    try:
        items, failed = _social_query(query, since, platform, hosts, name, limit=5)
    except Exception as exc:
        return FetchReport(name, "gagal", f"Sumber tidak tersedia. Pencarian {name} gagal: {exc.__class__.__name__}: {exc}")
    if not items and failed:
        return FetchReport(name, "gagal", f"Sumber tidak tersedia. Tautan {name} tidak berhasil diurai ke unggahan asli.")
    if not items:
        return FetchReport(name, "berhasil", f"Pencarian {name} tidak menemukan unggahan baru yang memuat kata kunci.", [])
    note = ""
    if platform == "facebook":
        note = " Facebook menolak pemeriksaan otomatis, tetapi tautan yang disimpan adalah permalink unggahan."
    return FetchReport(name, "berhasil", f"{len(items)} unggahan {name} dengan tautan asli.{note}", items)


def _social_query(query: str, since: datetime, platform: str, hosts: tuple[str, ...], label: str, limit: int) -> tuple[list[RawItem], int]:
    address = (
        "https://news.google.com/rss/search?q="
        + quote(f"{_exclude_owned_sites(query)} when:14d")
        + "&hl=id&gl=ID&ceid=ID:id"
    )
    raw_items = read_rss(address, platform, 2)
    kept: list[RawItem] = []
    failed = 0
    tried = 0
    for item in raw_items:
        if item.published_at < since or not _social_relevant(item):
            continue
        if len(kept) >= limit or tried >= 8:
            break
        tried += 1
        try:
            decoded = canonical_url(publisher_url(item.url))
        except Exception:
            failed += 1
            continue
        if not decoded or not _host_matches(decoded, hosts):
            failed += 1
            continue
        handle = _social_handle(decoded)
        if platform == "instagram" and not handle:
            from app.services.blocklist import lookup_author

            handle = lookup_author(decoded)
        spoken = _account_from_title(item.title)
        item.url = decoded
        item.platform = platform
        item.author_handle = handle
        item.author_name = handle.lstrip("@") or spoken or label
        item.source_name = item.author_name
        item.source_tier = 3
        item.credibility = 55
        if _owned(item):
            continue
        kept.append(item)
        time.sleep(0.2)
    return kept, failed


def _social_relevant(item: RawItem) -> bool:
    hay = f"{item.title}\n{item.text}".casefold()
    terms = (
        "bank indonesia",
        "bi-rate",
        "bi-fast",
        "qris",
        "kpw",
        "sobatrupiah",
        "suku bunga acuan",
    )
    return any(term in hay for term in terms)


def _host_matches(url: str, hosts: tuple[str, ...]) -> bool:
    host = urlsplit(url).netloc.lower()
    return any(host == name or host.endswith("." + name) for name in hosts)


def _account_from_title(title: str) -> str:
    """Google News menulis 'Nama Akun on Instagram: ...'. Nama itu yang dicek ke blocklist."""
    text = title or ""
    for marker in (" on Instagram:", " on TikTok:", " on Facebook:", " on X:", " on Twitter:"):
        index = text.casefold().find(marker.casefold())
        if index > 0:
            return text[:index].strip().strip('"')
    return ""


def _social_handle(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    segments = [piece for piece in parts.path.split("/") if piece]
    if not segments:
        return ""
    if "tiktok.com" in host and segments[0].startswith("@"):
        return segments[0]
    if host.endswith("x.com") or host.endswith("twitter.com"):
        if segments[0] not in {"i", "intent", "share", "search", "home"}:
            return "@" + segments[0]
    if "facebook.com" in host and segments[0] not in {"share", "watch", "reel", "story.php", "permalink.php", "posts"}:
        return segments[0]
    if "instagram.com" in host and segments[0] not in {"reel", "p", "stories", "tv", "explore"}:
        return "@" + segments[0]
    return ""


def _host_label(url: str) -> str:
    host = url.split("/")[2].replace("www.", "")
    known = {
        "detik.com": "Detik",
        "finance.detik.com": "Detik",
        "kompas.com": "Kompas",
        "cnbcindonesia.com": "CNBC Indonesia",
        "kontan.co.id": "Kontan",
        "bisnis.com": "Bisnis.com",
        "cnnindonesia.com": "CNN Indonesia",
        "tempo.co": "Tempo",
        "antaranews.com": "Antara",
        "liputan6.com": "Liputan6",
        "bloombergtechnoz.com": "Bloomberg Technoz",
        "beritajakarta.id": "Berita Jakarta",
        "tribunnews.com": "Warta Kota",
        "hukumonline.com": "Hukumonline",
    }
    for domain, label in known.items():
        if host == domain or host.endswith("." + domain):
            return label
    return host


def _gdelt_date(value: str | None) -> datetime | None:
    if not value or len(value) < 14:
        return None
    try:
        parsed = datetime.strptime(value[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    from zoneinfo import ZoneInfo

    return parsed.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Jakarta")).replace(tzinfo=None)
