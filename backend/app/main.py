"""API Media Monitor KPw BI DKI Jakarta.

Jalankan dari folder backend:
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.database import SessionLocal, init_db
from app.env import load_env
from app.routers.api import router
from app.scheduler import start_scheduler, stop_scheduler
from app.seed import purge_mock, seed_if_empty

load_env()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        purge_mock(db)
        from app.services.blocklist import apply_blocklist, ensure_defaults

        ensure_defaults(db)
        apply_blocklist(db)
        from app.services.keyword_watch import ensure_watch_keywords
        from app.services.pipeline import retag

        if ensure_watch_keywords(db):
            retag(db)
        from app.services.dss import refresh_advices

        refresh_advices(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Media Monitor KPw BI DKI Jakarta",
    version="0.2.0",
    description="Pemantauan media dari RSS dan API resmi. Sumber yang gagal tidak diisi data karangan.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _mount_frontend() -> None:
    index = DIST / "index.html"
    if not index.is_file():
        return
    root = DIST.resolve()

    @app.get("/", include_in_schema=False)
    def spa_index():
        return FileResponse(index)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = (DIST / full_path).resolve()
        if candidate.is_file() and str(candidate).startswith(str(root)):
            return FileResponse(candidate)
        return FileResponse(index)


_mount_frontend()
