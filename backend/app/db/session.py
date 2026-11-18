from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


database_url = settings().database_url
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False, "timeout": 15} if database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


if database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")


def session():
    with SessionLocal() as db:
        yield db


def check_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
