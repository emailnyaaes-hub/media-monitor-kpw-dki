"""Mengurai tautan Google News RSS menjadi URL penerbit.

Memakai endpoint decode milik Google News untuk tautan yang sudah ada di feed RSS.
Isi artikel penerbit tidak diunduh dan tidak disimpan.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urlparse

from app.connectors.http_util import fetch_bytes


def publisher_url(google_url: str) -> str:
    parsed = urlparse(google_url)
    pieces = [part for part in parsed.path.split("/") if part]
    if parsed.hostname != "news.google.com" or len(pieces) < 2 or pieces[-2] not in {"articles", "read"}:
        return ""
    token = pieces[-1]
    html = fetch_bytes(
        f"https://news.google.com/rss/articles/{token}",
        headers={"User-Agent": "Mozilla/5.0"},
        attempts=2,
    ).decode("utf-8", "replace")
    signature = re.search(r'data-n-a-sg="([^"]+)"', html)
    timestamp = re.search(r'data-n-a-ts="([^"]+)"', html)
    if not signature or not timestamp:
        return ""
    inner = (
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
        f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{token}",{timestamp.group(1)},"{signature.group(1)}"]'
    )
    payload = json.dumps([[["Fbv4je", inner]]])
    body = f"f.req={quote(payload)}".encode()
    raw = fetch_bytes(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": "Mozilla/5.0",
        },
        attempts=2,
    ).decode("utf-8", "replace")
    parsed_data = json.loads(raw.split("\n\n", 1)[1])
    decoded = json.loads(parsed_data[0][2])[1]
    if not isinstance(decoded, str) or not decoded.startswith("http"):
        return ""
    return decoded
