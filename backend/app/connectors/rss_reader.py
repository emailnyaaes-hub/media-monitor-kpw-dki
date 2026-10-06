"""Membaca RSS publik. Hanya judul, tanggal, nama sumber, dan cuplikan pendek yang disimpan."""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from app.connectors.base import RawItem
from app.connectors.http_util import fetch_bytes

WIB = ZoneInfo("Asia/Jakarta")


def strip_snippet(raw: str, limit: int = 360) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=WIB)
    return parsed.astimezone(WIB).replace(tzinfo=None)


def read_rss(url: str, source_name: str, source_tier: int) -> list[RawItem]:
    payload = fetch_bytes(url)
    root = ElementTree.fromstring(payload)
    items: list[RawItem] = []
    for node in root.findall(".//item"):
        title = strip_snippet(node.findtext("title") or "", 240)
        link = (node.findtext("link") or node.findtext("guid") or "").strip()
        if not title or not link.startswith("http"):
            continue
        description = node.findtext("description") or ""
        published = parse_date(node.findtext("pubDate")) or datetime.now()
        items.append(
            RawItem(
                source_name=source_name,
                source_tier=source_tier,
                platform="berita",
                url=link,
                author_name=source_name,
                author_handle="",
                published_at=published,
                title=title,
                text=strip_snippet(description) or "Cuplikan tidak tersedia di feed. Buka sumber asli.",
                reach_estimate=0,
                credibility=80 if source_tier == 1 else 65,
            )
        )
    return items


ATOM = "http://www.w3.org/2005/Atom"
MRSS = "http://search.yahoo.com/mrss/"
YT = "http://www.youtube.com/xml/schemas/2015"


def read_atom(url: str, source_tier: int, platform: str, handle: str = "") -> list[RawItem]:
    """Membaca feed Atom publik, termasuk feed kanal YouTube."""
    root = ElementTree.fromstring(fetch_bytes(url))
    items: list[RawItem] = []
    for node in root.findall(f"{{{ATOM}}}entry"):
        title = strip_snippet(node.findtext(f"{{{ATOM}}}title") or "", 240)
        href = ""
        for link in node.findall(f"{{{ATOM}}}link"):
            if link.attrib.get("rel", "alternate") == "alternate" and link.attrib.get("href"):
                href = link.attrib["href"]
                break
        if not href:
            video_id = node.findtext(f"{{{YT}}}videoId") or ""
            if video_id:
                href = f"https://www.youtube.com/watch?v={video_id}"
        published = parse_date(node.findtext(f"{{{ATOM}}}published") or node.findtext(f"{{{ATOM}}}updated"))
        author = node.findtext(f"{{{ATOM}}}author/{{{ATOM}}}name") or ""
        description = (
            node.findtext(f"{{{MRSS}}}group/{{{MRSS}}}description")
            or node.findtext(f"{{{ATOM}}}content")
            or ""
        )
        if not title or not href.startswith("http") or published is None:
            continue
        items.append(
            RawItem(
                source_name=author or "YouTube",
                source_tier=source_tier,
                platform=platform,
                url=href,
                author_name=author,
                author_handle=handle,
                published_at=published,
                title=title,
                text=strip_snippet(description) or "Cuplikan tidak tersedia di feed. Buka sumber asli.",
                reach_estimate=0,
                credibility=80 if source_tier == 1 else 65,
            )
        )
    return items
