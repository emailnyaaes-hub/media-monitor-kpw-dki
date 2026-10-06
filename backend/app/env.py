"""Memuat kunci dari backend/.env tanpa menimpa environment yang sudah ada."""

from __future__ import annotations

import os
from pathlib import Path


def load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    for path in (root / ".env", root.parent / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
