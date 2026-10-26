#!/usr/bin/env python3
"""Salin isi SQLite (seed atau monitor lokal) ke Postgres. Aman dijalankan ulang: tabel yang sudah berisi dilewati."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ORDER = [
    "users",
    "keywords",
    "blocked_sources",
    "saved_queries",
    "alert_rules",
    "issues",
    "mentions",
    "alerts",
    "audit_logs",
    "channel_posts",
    "connector_runs",
    "advices",
    "advice_revisions",
    "app_meta",
]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _source() -> Path:
    local = ROOT / "backend" / "data" / "monitor.db"
    seed = ROOT / "backend" / "seed" / "seed.db"
    if local.is_file() and seed.is_file():
        with sqlite3.connect(f"file:{local}?mode=ro", uri=True) as conn:
            local_max = conn.execute("select max(published_at) from mentions").fetchone()[0]
        with sqlite3.connect(f"file:{seed}?mode=ro", uri=True) as conn:
            seed_max = conn.execute("select max(published_at) from mentions").fetchone()[0]
        return local if (local_max or "") >= (seed_max or "") else seed
    return local if local.is_file() else seed


def main() -> None:
    _load_dotenv(ROOT / ".env.vercel.local")
    from sqlalchemy import Boolean, text

    from app.database import IS_SQLITE, Base, engine
    from app import models  # noqa: F401

    if IS_SQLITE:
        raise SystemExit("URL Postgres tidak terbaca. Tarik env Vercel dulu.")

    source = _source()
    if not source.is_file():
        raise SystemExit(f"SQLite tidak ada: {source}")
    print(f"sumber: {source.name}")

    Base.metadata.create_all(bind=engine)
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    with engine.begin() as dst:
        for name in ORDER:
            table = Base.metadata.tables[name]
            existing = dst.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() or 0
            if existing:
                print(f"{name}: sudah ada {existing}, dilewati")
                continue
            rows = src.execute(f"SELECT * FROM {name}").fetchall()
            if not rows:
                print(f"{name}: kosong")
                continue
            bool_cols = {col.name for col in table.columns if isinstance(col.type, Boolean)}
            parents: dict[str, set] = {}
            for fk in table.foreign_keys:
                parents.setdefault(fk.column.table.name, set())
            for parent in parents:
                parents[parent] = set(dst.execute(text(f"SELECT id FROM {parent}")).scalars().all())
            payload = []
            skipped = 0
            for row in rows:
                item = dict(row)
                for col in bool_cols:
                    if item.get(col) is not None:
                        item[col] = bool(item[col])
                drop = False
                for fk in table.foreign_keys:
                    value = item.get(fk.parent.name)
                    if value is None:
                        continue
                    if value not in parents.get(fk.column.table.name, set()):
                        if fk.parent.nullable:
                            item[fk.parent.name] = None
                        else:
                            drop = True
                if drop:
                    skipped += 1
                    continue
                payload.append(item)
            if skipped:
                print(f"{name}: {skipped} baris yatim dibuang")
            dst.execute(table.insert(), payload)
            print(f"{name}: {len(payload)}")

        for name in ORDER:
            table = Base.metadata.tables[name]
            if "id" not in table.c:
                continue
            seq = dst.execute(text("SELECT pg_get_serial_sequence(:table, 'id')"), {"table": name}).scalar()
            if not seq:
                continue
            dst.execute(
                text(f"SELECT setval(:seq, GREATEST(COALESCE((SELECT MAX(id) FROM {name}), 1), 1))"),
                {"seq": seq},
            )
    src.close()
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM mentions")).scalar()
        latest = conn.execute(text("SELECT MAX(published_at) FROM mentions")).scalar()
    print(f"mentions={count} terbaru={latest}")


if __name__ == "__main__":
    main()
