"""Menjalankan satu putaran pengambilan sumber asli."""

from app.database import SessionLocal, init_db
from app.env import load_env
from app.seed import purge_mock, seed_if_empty
from app.services.pipeline import ingest


def main() -> None:
    load_env()
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        purge_mock(db)
        from app.services.blocklist import apply_blocklist, ensure_defaults

        ensure_defaults(db)
        apply_blocklist(db)
        print(ingest(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
