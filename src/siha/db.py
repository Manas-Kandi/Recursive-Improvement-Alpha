"""Database setup and session management"""

from sqlmodel import SQLModel, create_engine, Session, text
from contextlib import contextmanager
from pathlib import Path
import os


# Database path
DB_PATH = Path(__file__).parent.parent.parent / "harness.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


def get_engine():
    """Create database engine with WAL mode for concurrent access"""
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    
    # Enable WAL mode for better concurrency
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()
    
    return engine


engine = get_engine()


def init_db():
    """Initialize database tables via Alembic migrations."""
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(Path(__file__).parent.parent.parent / "alembic.ini")
    command.upgrade(alembic_cfg, "head")


@contextmanager
def get_session():
    """Context manager for database sessions"""
    with Session(engine, expire_on_commit=False) as session:
        yield session
