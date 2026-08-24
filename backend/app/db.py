"""The single SQLAlchemy engine and session factory used throughout the app.

Every request handler calls `SessionLocal()` to get a session, uses it, and
closes it in a `finally` block -- there is no Flask-SQLAlchemy or
request-scoped session magic here, just plain SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
