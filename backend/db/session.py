"""
Database connection.

Reads ``DATABASE_URL`` when present (Render/Neon/Heroku-style managed
Postgres), otherwise composes a URL from DB_HOST, DB_PORT, DB_NAME,
DB_USER, DB_PASSWORD (see .env.example). A .env file is loaded if one
exists so `python -m backend.db.load_real_data` works without exporting
variables by hand.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "social_sentiment")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")


def _normalise_url(url: str) -> str:
    """Coerces managed-Postgres URLs into the psycopg2 SQLAlchemy dialect.

    Providers hand out ``postgres://`` (Heroku legacy) or
    ``postgresql://``. SQLAlchemy 2 needs an explicit driver. Managed
    Postgres also refuses plaintext connections, so TLS is required unless
    the host is local.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]

    host = (urlsplit(url).hostname or "").lower()
    local_hosts = {"", "localhost", "127.0.0.1", "::1", "db"}
    if host not in local_hosts and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


DATABASE_URL = _normalise_url(
    os.environ.get("DATABASE_URL")
    or f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
    max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "5")),
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency: yields a session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
