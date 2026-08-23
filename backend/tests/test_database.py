"""Tests for app.database module."""

from collections.abc import Generator
from unittest.mock import MagicMock

from app.database import create_db_and_tables, get_session, _dispose_engine, _set_sqlite_pragmas
from sqlmodel import Session


def test_create_db_and_tables() -> None:
    """Calling create_db_and_tables should not raise."""
    create_db_and_tables()


def test_get_session_yields_session() -> None:
    """get_session generator should yield a Session instance."""
    gen: Generator[Session, None, None] = get_session()
    session = next(gen)
    assert isinstance(session, Session)
    try:
        next(gen)
    except StopIteration:
        pass


def test_dispose_engine() -> None:
    """_dispose_engine should run without error."""
    _dispose_engine()


def test_set_sqlite_pragmas_skips_non_sqlite_connection() -> None:
    """The pragma callback should return early for non-sqlite connections."""
    result = _set_sqlite_pragmas(MagicMock(), None)
    assert result is None
