import atexit
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Apply performance-oriented PRAGMAs to new SQLite connections."""
    import sqlite3
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-8000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA mmap_size=268435456")
    cursor.close()


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite
    pool_pre_ping=True,
)

from sqlalchemy import event  # noqa: E402
event.listen(engine, "connect", _set_sqlite_pragmas)


@atexit.register
def _dispose_engine() -> None:
    """Ensure the engine pool is disposed on process exit to avoid ResourceWarnings."""
    engine.dispose()


def create_db_and_tables() -> None:
    """Create all database tables defined by SQLModel metadata."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLModel Session for the lifespan of the request."""
    with Session(engine) as session:
        yield session
