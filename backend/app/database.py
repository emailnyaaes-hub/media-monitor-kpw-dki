"""Koneksi basis data.

MVP memakai SQLite agar bisa dijalankan tanpa instalasi PostgreSQL.
Skema tabel sengaja sama dengan skrip docs/SKEMA.sql (PostgreSQL).
Untuk produksi, ganti BI_DATABASE_URL menjadi URL PostgreSQL.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SEED_DB = Path(__file__).resolve().parent.parent / "seed" / "seed.db"


def _on_vercel() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV") or os.environ.get("VERCEL_REGION"))


def _data_dir() -> Path:
    # Vercel filesystem is read-only except /tmp.
    override = os.environ.get("BI_DATA_DIR", "").strip()
    if override:
        path = Path(override)
    elif _on_vercel():
        path = Path("/tmp/danita-data")
    else:
        path = Path(__file__).resolve().parent.parent / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mention_count(db_path: Path) -> int:
    if not db_path.is_file() or db_path.stat().st_size < 1000:
        return 0
    try:
        import sqlite3

        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            return int(conn.execute("select count(*) from mentions").fetchone()[0])
    except Exception:
        return 0


def _ensure_seed(data_dir: Path) -> None:
    """Salin seed.db ke lokasi kerja bila database masih kosong (mis. cold start Vercel)."""
    target = data_dir / "monitor.db"
    if not SEED_DB.is_file():
        return
    if _mention_count(target) > 0:
        return
    shutil.copy2(SEED_DB, target)


DATA_DIR = _data_dir()
_ensure_seed(DATA_DIR)

DEFAULT_URL = f"sqlite:///{DATA_DIR / 'monitor.db'}"
DATABASE_URL = os.environ.get("BI_DATABASE_URL", DEFAULT_URL)

connect_args = {"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from sqlalchemy import inspect, text

    from app import models  # noqa: F401  — daftarkan tabel sebelum create_all

    Base.metadata.create_all(bind=engine)
    if not DATABASE_URL.startswith("sqlite"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("mentions")}
    if "quotes_bi" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE mentions ADD COLUMN quotes_bi BOOLEAN NOT NULL DEFAULT 0"))
    columns = {column["name"] for column in inspect(engine).get_columns("mentions")}
    with engine.begin() as connection:
        if "voice_override" not in columns:
            connection.execute(text("ALTER TABLE mentions ADD COLUMN voice_override TEXT NOT NULL DEFAULT ''"))
        if "segment_override" not in columns:
            connection.execute(text("ALTER TABLE mentions ADD COLUMN segment_override TEXT NOT NULL DEFAULT ''"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
