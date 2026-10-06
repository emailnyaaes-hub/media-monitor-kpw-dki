"""Menolak kanal milik Bank Indonesia. Mention yang lolos adalah pihak eksternal."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.models import BlockedSource, Mention

DEFAULTS = [
    ("domain", "bi.go.id", "Situs resmi Bank Indonesia dan seluruh subdomainnya"),
    ("account", "bank_indonesia*", "Akun resmi BI di semua platform, termasuk kantor perwakilan"),
    ("account", "bankindonesiaofficial", "Halaman Facebook resmi Bank Indonesia"),
    ("account", "bankindonesiachannel", "Kanal video resmi Bank Indonesia"),
    ("account", "ucv7sysolkpbhybdiwt7gzbg", "ID kanal YouTube Bank Indonesia Channel"),
    ("account", "kpwbi*", "Akun kantor perwakilan BI"),
    ("account", "kpw_bi*", "Akun kantor perwakilan BI"),
    ("account", "kpwbidki*", "Akun KPw BI DKI Jakarta"),
    ("account", "bikaltim", "Halaman resmi BI Kalimantan Timur"),
    ("channel", "Bank Indonesia", "Nama tampilan akun resmi pusat"),
    ("channel", "Bank Indonesia Channel", "Nama kanal YouTube resmi"),
    ("channel", "Bank Indonesia Institute", "Kanal lembaga internal BI"),
]

QUOTE_PATTERNS = (
    r"bank indonesia(?:\s*\(\s*bi\s*\))?\s+(mengatakan|menyatakan|mencatat|memutuskan|mengumumkan|menegaskan|menyampaikan|melaporkan|menahan|mempertahankan|mengucapkan|mendorong|meramal|memperketat|berhasil|siap|menetapkan|memproyeksikan)",
    r"\bbi\b (memutuskan|menahan|mencatat|mengumumkan|menyatakan|mempertahankan|putuskan|tahan|perketat|dorong|ungkap|umumkan|tetapkan)",
    r"menurut (bank indonesia|\bbi\b)",
    r"siaran pers",
    r"gubernur (bi|bank indonesia)",
    r"deputi gubernur",
    r"\brt\b",
    r"repost",
    r"mengutip",
    r"kutipan",
)


@dataclass
class BlockRule:
    kind: str
    value: str
    is_active: bool = True


def ensure_defaults(db: Session) -> None:
    if db.query(BlockedSource).count():
        return
    for kind, value, note in DEFAULTS:
        db.add(BlockedSource(kind=kind, value=value, note=note, is_active=True))
    db.commit()


def load_rules(db: Session) -> list[BlockRule]:
    rows = db.query(BlockedSource).filter(BlockedSource.is_active.is_(True)).all()
    return [BlockRule(row.kind, row.value, row.is_active) for row in rows]


def is_blocked(url: str, handle: str, author_name: str, source_name: str, title: str, rules: list[BlockRule]) -> bool:
    parts = urlsplit(url or "")
    host = parts.netloc.casefold().removeprefix("www.")
    path = parts.path.casefold()
    segments = [piece.lstrip("@") for piece in path.split("/") if piece]
    handle_norm = _norm(handle)
    names = {_norm(author_name), _norm(source_name)}
    title_norm = (title or "").casefold()
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.kind == "domain":
            domain = rule.value.casefold().strip().removeprefix("www.")
            if domain and (host == domain or host.endswith("." + domain)):
                return True
        elif rule.kind == "account":
            token = _norm(rule.value)
            prefix = token.endswith("*")
            token = token[:-1] if prefix else token
            if not token:
                continue
            candidates = [handle_norm, *segments]
            if prefix:
                if any(item.startswith(token) for item in candidates if item):
                    return True
            elif token in candidates or token in names:
                return True
        elif rule.kind == "channel":
            label = rule.value.casefold().strip()
            if not label:
                continue
            if _norm(author_name) == _norm(label) or _norm(source_name) == _norm(label):
                return True
            if title_norm.endswith(label) or f"- {label}" in title_norm:
                return True
    return False


def cites_bi(title: str, text: str) -> bool:
    hay = f"{title}\n{text}".casefold()
    return any(re.search(pattern, hay) for pattern in QUOTE_PATTERNS)


def external_only(query: Query, rules: list[BlockRule]) -> Query:
    """Jaring terakhir agar kanal BI tidak masuk KPI, explorer, maupun ekspor."""
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.kind == "domain":
            domain = rule.value.casefold().strip().removeprefix("www.")
            if domain:
                query = query.filter(~func.lower(Mention.url).contains(domain))
        elif rule.kind == "account":
            token = _norm(rule.value).rstrip("*")
            if len(token) < 4:
                continue
            handle = func.lower(func.coalesce(Mention.author_handle, ""))
            url = func.lower(func.coalesce(Mention.url, ""))
            query = query.filter(~handle.contains(token))
            query = query.filter(~url.contains("/" + token))
            query = query.filter(~url.contains("/@" + token))
        elif rule.kind == "channel":
            label = rule.value.casefold().strip()
            if not label:
                continue
            query = query.filter(func.lower(func.coalesce(Mention.author_name, "")) != label)
            query = query.filter(func.lower(func.coalesce(Mention.source_name, "")) != label)
    return query


def apply_blocklist(db: Session) -> int:
    from app.services.clustering import rebuild_issues

    rules = load_rules(db)
    removed = 0
    for row in db.query(Mention).all():
        discovered = ""
        nameless = _norm(row.author_handle) in {"", "instagram", "youtube", "youtube.com"}
        if nameless and ("instagram.com" in (row.url or "") or "youtube.com" in (row.url or "") or "youtu.be" in (row.url or "")):
            discovered = lookup_author(row.url)
        if discovered:
            row.author_handle = discovered[:120]
            row.author_name = discovered[:120]
            if _norm(row.source_name) in {"", "instagram", "youtube", "youtube.com"}:
                row.source_name = discovered[:120]
        if is_blocked(row.url, row.author_handle, row.author_name, row.source_name, row.title, rules):
            db.delete(row)
            removed += 1
            continue
        row.quotes_bi = cites_bi(row.title, row.text)
    db.commit()
    if removed:
        rebuild_issues(db)
    return removed


def lookup_author(url: str) -> str:
    """Nama akun dari oEmbed publik. Dipakai bila permalink tidak memuat username."""
    from urllib.parse import quote

    from app.connectors.http_util import fetch_bytes

    text = url or ""
    host = urlsplit(text).netloc.casefold()
    if "instagram.com" in host and ("/p/" in text or "/reel/" in text):
        endpoint = "https://www.instagram.com/api/v1/oembed/?url=" + quote(text)
    elif "youtube.com" in host or "youtu.be" in host:
        endpoint = "https://www.youtube.com/oembed?format=json&url=" + quote(text)
    else:
        return ""
    try:
        payload = json.loads(fetch_bytes(endpoint).decode("utf-8", "replace"))
    except Exception:
        return ""
    return (payload.get("author_name") or "").strip().lstrip("@")


def _norm(value: str) -> str:
    return (value or "").strip().casefold().lstrip("@")
