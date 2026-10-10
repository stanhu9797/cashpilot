"""Database engine and session. SQLite locally, PostgreSQL in production."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import ROOT_DIR, get_settings

settings = get_settings()
url = settings.database_url or f"sqlite:///{ROOT_DIR / 'backend' / 'cashpilot.db'}"
if url.startswith("postgres://"):  # some hosts hand out this older prefix
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(bind=engine)
