"""Pengambilan HTTP dengan retry. Isi halaman tidak disimpan."""

from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def fetch_bytes(url: str, *, timeout: int = 20, attempts: int = 3, data: bytes | None = None, headers: dict | None = None) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                last_error = exc
                continue
            raise
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("Pengambilan gagal")
