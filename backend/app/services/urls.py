"""URL kanonik dan pemeriksaan status HTTP.

Parameter pelacak dibuang. Tubuh halaman tidak disimpan.
"""

from __future__ import annotations

import http.client
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "oc", "soc_src", "soc_trk",
}

BROWSER = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def canonical_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in TRACKING]
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def http_status(url: str, hops: int = 4) -> int:
    """Kembalikan status HTTP terakhir. Redirect diikuti, isi halaman dibuang."""
    current = url
    for _ in range(hops):
        parts = urlsplit(current)
        connection_cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        connection = connection_cls(parts.netloc, timeout=12)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        try:
            connection.request("GET", path, headers={"User-Agent": BROWSER, "Range": "bytes=0-0"})
            response = connection.getresponse()
            status = response.status
            location = response.getheader("Location")
            response.read(32)
        finally:
            connection.close()
        if status in {301, 302, 303, 307, 308} and location:
            if location.startswith("/"):
                current = f"{parts.scheme}://{parts.netloc}{location}"
            else:
                current = location
            continue
        return status
    return 0


def is_public_article(url: str) -> bool:
    lowered = url.lower()
    if "news.google.com" in lowered or "contoh.media-monitor.local" in lowered:
        return False
    try:
        status = http_status(url)
    except Exception:
        return False
    if _facebook_permalink(url) and status in {400, 401, 403}:
        # Facebook mengembalikan halaman "Error" untuk semua URL, termasuk halaman resmi, bila diminta program.
        return True
    return 200 <= status < 400


def _facebook_permalink(url: str) -> bool:
    parts = urlsplit(url)
    if "facebook.com" not in parts.netloc.lower():
        return False
    path = parts.path.lower()
    if not any(piece in path for piece in ("/posts/", "/videos/", "/reel/", "/photos/")):
        return False
    return any(character.isdigit() for character in path)
