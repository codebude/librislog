"""Full backup and restore service — VACUUM INTO, ZIP creation, safety rollback."""

import json
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from app._build_info import __version__
from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)


TOTAL_MAX_EXTRACT_SIZE: int = 1024 * 1024 * 1024  # 1 GB
MAX_EXTRACT_FILE_COUNT: int = 100_000
MAX_SINGLE_FILE_SIZE: int = 500 * 1024 * 1024

_lock_fd: int | None = None
_LOCK_FILE: str = "backup_restore.lock"


def _remove_wal_files(db_path: str) -> None:
    """Remove stale WAL and SHM files left by a WAL-mode database.

    Must be called after replacing the database file on disk and before
    opening any new connection, otherwise SQLite will try to replay the old
    WAL into the new database — causing B‑tree corruption.
    """
    for suffix in ("-wal", "-shm"):
        path = f"{db_path}{suffix}"
        if os.path.isfile(path):
            os.remove(path)


def _run_alembic_migrations() -> None:
    """Run all pending alembic migrations to bring the database schema up to date.

    This is necessary when restoring a backup from an older release whose schema
    may be behind the current codebase.
    """
    from alembic.config import Config
    from alembic.command import upgrade

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    upgrade(alembic_cfg, "head")


def _stamp_alembic_head_if_fresh() -> None:
    """Stamp alembic_version at the current head when the version table is absent
    or empty.

    After ``SQLModel.metadata.create_all()`` creates tables directly (bypassing
    alembic), alembic would otherwise try to re-run the initial migration and fail
    with *table already exists*.

    When ``alembic_version`` already has a row (e.g. an old backup was restored),
    stamping is skipped so that ``alembic upgrade head`` can apply pending
    migrations on top of whatever revision the backup was at.
    """
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory

    import sqlite3

    db_path = _extract_db_path(settings.database_url)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        )
        table_exists = cursor.fetchone() is not None
        if table_exists:
            row_count = conn.execute("SELECT COUNT(*) FROM alembic_version").fetchone()[0]
            if row_count > 0:
                return
    finally:
        conn.close()

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_cfg)
    head = script.get_current_head()
    if head:
        command.stamp(alembic_cfg, head)


def _recreate_engine() -> None:
    """Replace the global SQLAlchemy engine with a fresh one.

    Called after restoring the database on disk so the app picks up the new data.
    Also runs pending alembic migrations for backward compatibility with backups
    created by older releases.
    """
    from app.database import create_engine as _create_engine
    from sqlmodel import SQLModel
    import app.database as db_mod
    new_engine = _create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(new_engine)
    _stamp_alembic_head_if_fresh()
    _run_alembic_migrations()
    db_mod.engine = new_engine


def _acquire_operation_lock() -> None:
    """Acquire an exclusive file lock to prevent concurrent backup/restore."""
    global _lock_fd
    lock_path = os.path.join(settings.backup_temp_dir, _LOCK_FILE)
    Path(settings.backup_temp_dir).mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RuntimeError("Another backup or restore operation is already in progress") from exc
    _lock_fd = fd


def _release_operation_lock() -> None:
    """Release the exclusive file lock."""
    global _lock_fd
    if _lock_fd is not None:
        import fcntl
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(_lock_fd)
        _lock_fd = None


def _extract_db_path(database_url: str) -> str:
    """Extract the filesystem path from a ``sqlite:///`` URL."""
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    return database_url


def _validate_zip_extraction(zf: ZipFile) -> None:
    """Validate a ZIP archive against size and count limits.

    Raises:
        ValueError: If any limit is exceeded.
    """
    total_size = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        total_size += info.file_size
        if info.file_size > MAX_SINGLE_FILE_SIZE:
            raise ValueError(f"File {info.filename} exceeds maximum single file size of {MAX_SINGLE_FILE_SIZE} bytes")
    if total_size > TOTAL_MAX_EXTRACT_SIZE:
        raise ValueError(f"Total extraction size exceeds limit of {TOTAL_MAX_EXTRACT_SIZE} bytes")
    if len(zf.infolist()) > MAX_EXTRACT_FILE_COUNT:
        raise ValueError("Too many files in ZIP archive")


def _safe_extract_path(dest_root: Path, arcname: str) -> Path:
    """Resolve *arcname* relative to *dest_root*, rejecting path traversal.

    Raises:
        ValueError: On absolute paths, empty paths, or traversal attempts.
    """
    if os.path.isabs(arcname):
        raise ValueError(f"Absolute path not allowed: {arcname}")
    parts = arcname.replace("\\", "/").split("/")
    cleaned = [p for p in parts if p and p not in (".", "..")]
    if not cleaned:
        raise ValueError(f"Empty path after normalization: {arcname}")
    resolved = (dest_root / "/".join(cleaned)).resolve()
    if not str(resolved).startswith(str(dest_root.resolve())):
        raise ValueError(f"Path traversal detected: {arcname}")
    return resolved


def _vacuum_into_backup(database_url: str, dest_path: str) -> None:
    """Run ``VACUUM INTO`` on the database to create a compact backup copy.

    NOTE: sqlite3.connect() context manager manages transactions, NOT
    the connection itself. Always use explicit conn.close() in a finally block.
    """
    db_path = _extract_db_path(database_url)
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM INTO ?", (dest_path,))
    finally:
        conn.close()
    if not os.path.isfile(dest_path):
        raise RuntimeError("VACUUM INTO did not produce a database file")


def create_backup(
    database_url: str,
    data_dir: str,
    covers_dir: str,
    import_temp_dir: str,
) -> bytes:
    """Create a full backup ZIP containing the database, covers, and import temp files.

    Args:
        database_url: SQLAlchemy database URL.
        data_dir: Root data directory.
        covers_dir: Cover storage directory.
        import_temp_dir: Import temporary files directory.

    Returns:
        ZIP archive as bytes.
    """
    _acquire_operation_lock()
    try:
        covers_path = Path(covers_dir)
        import_temp_path = Path(import_temp_dir)

        cover_count = 0
        if covers_path.is_dir():
            cover_count = sum(1 for _ in covers_path.iterdir() if _.is_file())

        temp_count = 0
        if import_temp_path.is_dir():
            temp_count = sum(1 for _ in import_temp_path.rglob("*") if _.is_file())

        db_size = os.path.getsize(_extract_db_path(database_url))

        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "app_version": __version__,
            "database_size_bytes": db_size,
            "covers_count": cover_count,
            "import_temp_files_count": temp_count,
        }

        backup_db_path = os.path.join(settings.backup_temp_dir, f"backup_{os.urandom(8).hex()}.db")
        Path(settings.backup_temp_dir).mkdir(parents=True, exist_ok=True)
        try:
            _vacuum_into_backup(database_url, backup_db_path)

            buf = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
            with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
                zf.write(backup_db_path, "database.db")
                zf.writestr("metadata.json", json.dumps(metadata, indent=2))

                if covers_path.is_dir():
                    for entry in sorted(covers_path.iterdir()):
                        if entry.is_file():
                            zf.write(str(entry), f"data/covers/{entry.name}")

                if import_temp_path.is_dir():
                    for entry in sorted(import_temp_path.rglob("*")):
                        if entry.is_file():
                            rel = entry.relative_to(import_temp_path)
                            zf.write(str(entry), f"data/import_temp/{rel}")

            buf.seek(0)
            data = buf.read()
            buf.close()
            return data
        finally:
            if os.path.isfile(backup_db_path):
                os.remove(backup_db_path)
    finally:
        _release_operation_lock()


def validate_backup_zip(zip_bytes: bytes) -> dict[str, Any]:
    """Validate a backup ZIP archive without extracting it.

    Args:
        zip_bytes: Raw ZIP file bytes.

    Returns:
        A dict with ``"valid"`` bool and optional ``"error"`` or ``"metadata"``.
    """
    metadata: dict[str, Any] = {}
    has_database = False
    has_data = False

    with tempfile.SpooledTemporaryFile(max_size=len(zip_bytes)) as buf:
        buf.write(zip_bytes)
        buf.seek(0)
        with ZipFile(buf, "r") as zf:
            _validate_zip_extraction(zf)
            names = zf.namelist()
            if "database.db" in names:
                has_database = True
            if any(n.startswith("data/") for n in names):
                has_data = True
            if "metadata.json" in names:
                info = zf.getinfo("metadata.json")
                if info.file_size > 10 * 1024 * 1024:
                    return {"valid": False, "error": "metadata.json is too large"}
                try:
                    metadata = json.loads(zf.read("metadata.json"))
                except (json.JSONDecodeError, KeyError):
                    metadata = {}

    if not has_database:
        return {"valid": False, "error": "Backup is missing database.db"}
    if not has_data:
        return {"valid": False, "error": "Backup is missing data/ directory"}

    return {"valid": True, "metadata": metadata}


def _save_safety_backup(database_url: str, data_dir: str) -> str:
    """Copy the current data directory to a temporary safety backup before restoring."""
    safety_dir = tempfile.mkdtemp(prefix="librislog_safety_", dir=data_dir)
    db_path = _extract_db_path(database_url)
    if os.path.isfile(db_path):
        shutil.copy2(db_path, os.path.join(safety_dir, "database.db"))
    data_path = Path(data_dir).resolve()
    backup_temp_resolved = Path(settings.backup_temp_dir).resolve()
    safety_resolved = Path(safety_dir).resolve()
    if data_path.is_dir():
        for item in data_path.iterdir():
            item_resolved = item.resolve()
            if item_resolved == safety_resolved or item_resolved == backup_temp_resolved:
                continue
            dest = os.path.join(safety_dir, item.name)
            if item.is_dir():
                shutil.copytree(str(item), dest)
            else:
                shutil.copy2(str(item), dest)
    return safety_dir


def _rollback_safety_backup(safety_dir: str, database_url: str, data_dir: str) -> None:
    """Restore files from the safety backup directory."""
    db_path = _extract_db_path(database_url)
    safety_db = os.path.join(safety_dir, "database.db")
    if os.path.isfile(safety_db):
        shutil.copy2(safety_db, db_path)
        _remove_wal_files(db_path)
    for item_name in os.listdir(safety_dir):
        if item_name == "database.db":
            continue
        src = os.path.join(safety_dir, item_name)
        dest = os.path.join(data_dir, item_name)
        if os.path.isdir(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def _cleanup_safety_backup(safety_dir: str) -> None:
    """Remove the safety backup directory."""
    try:
        shutil.rmtree(safety_dir)
    except OSError as exc:
        logger.warning("Failed to clean up safety backup %s: %s", safety_dir, exc)


def restore_backup(
    backup_zip_bytes: bytes,
    database_url: str,
    data_dir: str,
    covers_dir: str,
    import_temp_dir: str,
) -> dict[str, Any]:
    """Restore a backup ZIP archive, with rollback on failure.

    Args:
        backup_zip_bytes: Raw backup ZIP file bytes.
        database_url: SQLAlchemy database URL.
        data_dir: Root data directory.
        covers_dir: Cover storage directory.
        import_temp_dir: Import temporary files directory.

    Returns:
        A dict with ``"restored_books"`` and ``"restored_covers"`` counts.
    """
    _acquire_operation_lock()
    try:
        safety_dir = _save_safety_backup(database_url, data_dir)
        logger.info("Safety backup saved to %s", safety_dir)

        try:
            with tempfile.SpooledTemporaryFile(max_size=len(backup_zip_bytes)) as buf:
                buf.write(backup_zip_bytes)
                buf.seek(0)
                with ZipFile(buf, "r") as zf:
                    _validate_zip_extraction(zf)

                    data_path = Path(data_dir).resolve()
                    covers_path = Path(covers_dir)
                    import_temp_path = Path(import_temp_dir)

                    for d in [covers_path, import_temp_path]:
                        if d.is_dir():
                            shutil.rmtree(str(d))
                        d.mkdir(parents=True, exist_ok=True)

                    for entry_name in zf.namelist():
                        if entry_name in ("database.db", "metadata.json") or not entry_name.startswith("data/"):
                            continue
                        rel_part = entry_name[len("data/"):]
                        if not rel_part:
                            continue
                        dest = _safe_extract_path(data_path, rel_part)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if entry_name.endswith("/"):
                            dest.mkdir(parents=True, exist_ok=True)
                        else:
                            info = zf.getinfo(entry_name)
                            if info.file_size > MAX_SINGLE_FILE_SIZE:
                                raise ValueError(f"File {entry_name} exceeds maximum size")
                            dest.write_bytes(zf.read(entry_name))

                    restored_covers = 0
                    if covers_path.is_dir():
                        restored_covers = sum(1 for _ in covers_path.iterdir() if _.is_file())

                    backup_db = zf.read("database.db")

            engine.dispose()
            db_path = _extract_db_path(database_url)
            tmp_path = ""
            try:
                with tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(db_path)) as tmp:
                    tmp.write(backup_db)
                    tmp_path = tmp.name
                shutil.move(tmp_path, db_path)
            except Exception:
                if tmp_path and os.path.isfile(tmp_path):
                    os.remove(tmp_path)
                raise

            _remove_wal_files(db_path)

            tmp_db_path = _extract_db_path(database_url)
            # NOTE: sqlite3.connect() context manager manages transactions, NOT
            # the connection itself. See note in _vacuum_into_backup above.
            conn = sqlite3.connect(tmp_db_path)
            try:
                conn.execute("PRAGMA integrity_check")
                row = conn.execute("SELECT COUNT(*) FROM book").fetchone()
                restored_books = row[0] if row else 0
            finally:
                conn.close()

            _recreate_engine()

            _cleanup_safety_backup(safety_dir)
            logger.info("Safety backup cleaned up")

            return {
                "restored_books": restored_books,
                "restored_covers": restored_covers,
            }
        except Exception as exc:
            logger.exception("Restore failed, rolling back safety backup")
            _rollback_safety_backup(safety_dir, database_url, data_dir)
            _recreate_engine()
            _cleanup_safety_backup(safety_dir)
            raise RuntimeError(f"Restore failed and was rolled back: {exc}") from exc
    finally:
        _release_operation_lock()
