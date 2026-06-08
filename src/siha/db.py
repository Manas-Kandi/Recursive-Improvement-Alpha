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
    """Initialize database tables and apply lightweight migrations"""
    from siha.models import Task, Step, Tool, ToolCall, Prompt, Strategy, Mutation, Benchmark, BenchmarkRun, HarnessVersion
    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate():
    """Apply additive column migrations for pre-existing SQLite databases."""
    expected = {
        "task": {
            "final_answer": "TEXT",
            "analyzed": "BOOLEAN DEFAULT 0",
        },
    }
    with engine.connect() as conn:
        for table, columns in expected.items():
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            for column, ddl in columns.items():
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        conn.commit()


@contextmanager
def get_session():
    """Context manager for database sessions"""
    with Session(engine) as session:
        yield session
