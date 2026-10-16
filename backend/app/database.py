"""Koneksi basis data.

MVP memakai SQLite agar bisa dijalankan tanpa instalasi PostgreSQL.
Skema tabel sengaja sama dengan skrip docs/SKEMA.sql (PostgreSQL).
Untuk produksi, ganti BI_DATABASE_URL menjadi URL PostgreSQL.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def _data_dir() -> Path:
    # Vercel filesystem is read-only except /tmp.
    override = os.environ.get("BI_DATA_DIR", "").strip()
    if override:
        path = Path(override)
    elif os.environ.get("VERCEL") == "1":
        path = Path("/tmp/danita-data")
    else:
        path = Path(__file__).resolve().parent.parent / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = _data_dir()

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
