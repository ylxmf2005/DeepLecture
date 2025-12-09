"""SQLite database setup using SQLAlchemy."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from deeplecture.app_context import AppContext, get_app_context

logger = logging.getLogger(__name__)

# Global engine and session factory (single instance per process)
_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None
_db_initialized: bool = False


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL mode and foreign keys for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_engine(app_context: Optional[AppContext] = None) -> Engine:
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is not None:
        return _engine

    ctx = app_context or get_app_context()
    ctx.init_paths()

    db_path = os.path.join(ctx.data_dir, "deeplecture.db")
    _engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_pre_ping=True,
    )
    logger.info("Database initialized: %s", db_path)
    return _engine


def get_session_factory(app_context: Optional[AppContext] = None) -> sessionmaker:
    """Get or create the session factory."""
    global _SessionFactory
    if _SessionFactory is not None:
        return _SessionFactory

    engine = get_engine(app_context)
    _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    return _SessionFactory


@contextmanager
def get_session(app_context: Optional[AppContext] = None) -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit/rollback."""
    factory = get_session_factory(app_context)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(app_context: Optional[AppContext] = None) -> None:
    """Initialize the database and create all tables (idempotent)."""
    global _db_initialized
    if _db_initialized:
        return

    from deeplecture.storage.models import Base

    engine = get_engine(app_context)
    Base.metadata.create_all(engine)
    _db_initialized = True
    logger.info("Database tables created")
