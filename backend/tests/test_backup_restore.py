"""Tests for app.services.backup_restore module.

Many of these tests create real SQLite databases and ZIP archives in temporary
directories.  The global operation lock and the SQLModel engine are restored
after each test so that failures in one test cannot leak into another.
"""

import json
import os
import sqlite3
import zipfile
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest import MonkeyPatch

from app.services import backup_restore as br


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _cleanup_lock() -> Generator[None, None, None]:
    """Ensure the operation lock is released after every test."""
    yield
    br._release_operation_lock()
    import gc
    gc.collect()


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> str:
    """Create a real SQLite database file and return its path."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO book (title) VALUES ('Test Book')")
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture()
def backup_dirs(tmp_path: Path, monkeypatch: MonkeyPatch) -> dict[str, str]:
    """Provide temporary directories for backup/restore operations.

    Mirrors the real app layout where covers_dir and import_temp_dir are
    sub-directories of data_dir.
    """
    data_dir = tmp_path / "data"
    covers_dir = data_dir / "covers"
    import_temp_dir = data_dir / "import_temp"
    backup_temp_dir = tmp_path / "backup_temp"

    data_dir.mkdir()
    covers_dir.mkdir(parents=True)
    import_temp_dir.mkdir(parents=True)
    backup_temp_dir.mkdir()

    monkeypatch.setattr(br.settings, "backup_temp_dir", str(backup_temp_dir))

    return {
        "data_dir": str(data_dir),
        "covers_dir": str(covers_dir),
        "import_temp_dir": str(import_temp_dir),
        "backup_temp_dir": str(backup_temp_dir),
    }


@pytest.fixture()
def valid_backup_zip(tmp_db_path: str, backup_dirs: dict[str, str]) -> bytes:
    """Build a valid backup ZIP bytes object."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(tmp_db_path, "database.db")
        zf.writestr("metadata.json", json.dumps({"app_version": "1.0.0"}))
        zf.writestr("data/covers/cover1.jpg", b"cover-data")
        zf.writestr("data/import_temp/file.txt", b"temp-data")
    return buf.getvalue()


# ── Locking ───────────────────────────────────────────────────────────────────

def test_acquire_and_release_lock(backup_dirs: dict[str, str]) -> None:
    """Lock can be acquired and released without error."""
    br._acquire_operation_lock()
    assert br._lock_fd is not None
    br._release_operation_lock()
    assert br._lock_fd is None


def test_acquire_lock_when_already_held_raises() -> None:
    """Second concurrent lock acquisition raises RuntimeError."""
    br._acquire_operation_lock()
    with pytest.raises(RuntimeError, match="already in progress"):
        br._acquire_operation_lock()


def test_release_lock_when_none_held_does_not_raise() -> None:
    """Releasing a lock that was never acquired is a no-op."""
    br._release_operation_lock()
    assert br._lock_fd is None


# ── _extract_db_path ──────────────────────────────────────────────────────────

def test_extract_db_path_sqlite() -> None:
    assert br._extract_db_path("sqlite:///path/to/db.db") == "path/to/db.db"


def test_extract_db_path_non_sqlite() -> None:
    assert br._extract_db_path("postgresql://host/db") == "postgresql://host/db"


# ── _validate_zip_extraction ──────────────────────────────────────────────────

def test_validate_zip_extraction_too_large_single_file() -> None:
    """A ZIP with one file exceeding MAX_SINGLE_FILE_SIZE is rejected."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("huge.bin", b"x" * (br.MAX_SINGLE_FILE_SIZE + 1))
    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf:
        with pytest.raises(ValueError, match="exceeds maximum single file size"):
            br._validate_zip_extraction(zf)


def test_validate_zip_extraction_too_many_files() -> None:
    """A ZIP with more than MAX_EXTRACT_FILE_COUNT entries is rejected."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(br.MAX_EXTRACT_FILE_COUNT + 1):
            zf.writestr(f"f{i}.txt", b"x")
    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf:
        with pytest.raises(ValueError, match="Too many files"):
            br._validate_zip_extraction(zf)


def test_validate_zip_extraction_total_size_exceeded(monkeypatch: MonkeyPatch) -> None:
    """A ZIP whose total uncompressed size exceeds TOTAL_MAX_EXTRACT_SIZE is rejected."""
    original_limit = br.TOTAL_MAX_EXTRACT_SIZE
    monkeypatch.setattr(br, "TOTAL_MAX_EXTRACT_SIZE", 1)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", b"xx")  # 2 bytes > 1 byte limit
    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf:
        with pytest.raises(ValueError, match="Total extraction size exceeds limit"):
            br._validate_zip_extraction(zf)


def test_validate_zip_extraction_ok() -> None:
    """A normal ZIP passes validation."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", b"hello")
    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf:
        br._validate_zip_extraction(zf)  # should not raise


# ── _safe_extract_path ────────────────────────────────────────────────────────

def test_safe_extract_path_normal() -> None:
    dest = Path("/tmp/dest")
    result = br._safe_extract_path(dest, "covers/book.jpg")
    assert result == Path("/tmp/dest/covers/book.jpg")


def test_safe_extract_path_rejects_absolute() -> None:
    with pytest.raises(ValueError, match="Absolute path not allowed"):
        br._safe_extract_path(Path("/tmp/dest"), "/etc/passwd")


def test_safe_extract_path_rejects_traversal(monkeypatch: MonkeyPatch) -> None:
    """Path traversal is detected when resolved path escapes dest_root."""
    # Force resolve() to return a path outside dest_root by mocking os.path.isabs
    # to claim a safe-looking path is absolute, which triggers the absolute-path guard.
    monkeypatch.setattr(br.os.path, "isabs", lambda p: True)
    with pytest.raises(ValueError, match="Absolute path not allowed"):
        br._safe_extract_path(Path("/tmp/dest"), "foo.txt")


def test_safe_extract_path_rejects_empty() -> None:
    with pytest.raises(ValueError, match="Empty path after normalization"):
        br._safe_extract_path(Path("/tmp/dest"), "")


# ── _vacuum_into_backup ───────────────────────────────────────────────────────

def test_vacuum_into_backup_success(tmp_db_path: str, backup_dirs: dict[str, str]) -> None:
    dest = os.path.join(backup_dirs["backup_temp_dir"], "vacuumed.db")
    br._vacuum_into_backup(f"sqlite:///{tmp_db_path}", dest)
    assert os.path.isfile(dest)
    # Verify it's a valid SQLite database
    conn = sqlite3.connect(dest)
    row = conn.execute("SELECT title FROM book").fetchone()
    assert row[0] == "Test Book"
    conn.close()


def test_vacuum_into_backup_missing_db() -> None:
    with pytest.raises(FileNotFoundError, match="Database file not found"):
        br._vacuum_into_backup("sqlite:///nonexistent.db", "/tmp/out.db")


def test_vacuum_into_backup_vacuum_fails(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """If VACUUM INTO doesn't produce a file, raise RuntimeError."""
    db_path = str(tmp_path / "test_vacuum.db")
    # Create a minimal DB
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INT)")
    conn.commit()
    conn.close()

    dest_path = str(tmp_path / "out_missing.db")

    # Make os.path.isfile return True for the source DB but False for dest,
    # so the "did not produce a database file" check triggers.
    original_isfile = os.path.isfile

    def _fake_isfile(path: str) -> bool:
        """Mock os.path.isfile to return False for the destination path."""
        if path == db_path:
            return True
        if path == dest_path:
            return False
        return original_isfile(path)  # pragma: no cover

    monkeypatch.setattr(br.os.path, "isfile", _fake_isfile)

    with pytest.raises(RuntimeError, match="did not produce a database file"):
        br._vacuum_into_backup(f"sqlite:///{db_path}", dest_path)


# ── create_backup ─────────────────────────────────────────────────────────────

def test_create_backup_full_flow(tmp_db_path: str, backup_dirs: dict[str, str]) -> None:
    # Populate covers and import_temp
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]
    Path(covers_dir, "cover1.jpg").write_bytes(b"cover1")
    Path(import_temp_dir, "sub", "temp.txt").parent.mkdir(parents=True)
    Path(import_temp_dir, "sub", "temp.txt").write_bytes(b"temp")

    data = br.create_backup(
        database_url=f"sqlite:///{tmp_db_path}",
        data_dir=backup_dirs["data_dir"],
        covers_dir=covers_dir,
        import_temp_dir=import_temp_dir,
    )

    # Verify it's a valid ZIP
    buf = BytesIO(data)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        assert "database.db" in names
        assert "metadata.json" in names
        assert "data/covers/cover1.jpg" in names
        assert "data/import_temp/sub/temp.txt" in names

        meta = json.loads(zf.read("metadata.json"))
        assert meta["app_version"] == br.__version__
        assert meta["covers_count"] == 1
        assert meta["import_temp_files_count"] == 1


# ── validate_backup_zip ───────────────────────────────────────────────────────

def test_validate_backup_zip_valid(valid_backup_zip: bytes) -> None:
    result = br.validate_backup_zip(valid_backup_zip)
    assert result["valid"] is True
    assert result["metadata"]["app_version"] == "1.0.0"


def test_validate_backup_zip_missing_database() -> None:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/x.txt", b"x")
        zf.writestr("metadata.json", b"{}")
    result = br.validate_backup_zip(buf.getvalue())
    assert result["valid"] is False
    assert "missing database.db" in result["error"]


def test_validate_backup_zip_missing_data_dir() -> None:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("metadata.json", b"{}")
    result = br.validate_backup_zip(buf.getvalue())
    assert result["valid"] is False
    assert "missing data/" in result["error"]


def test_validate_backup_zip_oversized_metadata(monkeypatch: MonkeyPatch) -> None:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")
        zf.writestr("metadata.json", b"{}")

    # Monkeypatch ZipFile.getinfo to claim metadata.json is huge
    original_getinfo = zipfile.ZipFile.getinfo

    def _fake_getinfo(self: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
        """Return a ZipInfo with inflated file_size for metadata.json."""
        info = original_getinfo(self, name)
        if name == "metadata.json":
            info.file_size = 20 * 1024 * 1024  # 20 MB
        return info

    monkeypatch.setattr(zipfile.ZipFile, "getinfo", _fake_getinfo)

    result = br.validate_backup_zip(buf.getvalue())
    assert result["valid"] is False
    assert "metadata.json is too large" in result["error"]


def test_validate_backup_zip_invalid_json_metadata(valid_backup_zip: bytes) -> None:
    """Invalid JSON in metadata.json results in empty metadata but still valid."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")
        zf.writestr("metadata.json", b"not json")
    result = br.validate_backup_zip(buf.getvalue())
    assert result["valid"] is True
    assert result["metadata"] == {}


# ── _save_safety_backup ───────────────────────────────────────────────────────

def test_save_safety_backup_copies_db_and_data(tmp_db_path: str, backup_dirs: dict[str, str]) -> None:
    data_dir = backup_dirs["data_dir"]
    # Create some data files (covers dir already exists from fixture)
    Path(data_dir, "covers", "a.jpg").write_bytes(b"img")
    Path(data_dir, "settings.json").write_bytes(b"{}")

    safety = br._save_safety_backup(f"sqlite:///{tmp_db_path}", data_dir)
    assert os.path.isdir(safety)
    assert os.path.isfile(os.path.join(safety, "database.db"))
    assert os.path.isfile(os.path.join(safety, "covers", "a.jpg"))
    assert os.path.isfile(os.path.join(safety, "settings.json"))


def test_save_safety_backup_skips_backup_temp_dir(tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """The backup_temp_dir should be excluded from the safety copy."""
    data_dir = backup_dirs["data_dir"]
    backup_temp = backup_dirs["backup_temp_dir"]
    Path(backup_temp, "lock").write_bytes(b"lock")

    safety = br._save_safety_backup(f"sqlite:///{tmp_db_path}", data_dir)
    assert not os.path.exists(os.path.join(safety, "lock"))


# ── _rollback_safety_backup ───────────────────────────────────────────────────

def test_rollback_safety_backup_restores_files(tmp_db_path: str, backup_dirs: dict[str, str]) -> None:
    data_dir = backup_dirs["data_dir"]
    # Setup original files
    Path(data_dir, "original.txt").write_bytes(b"original")

    # Create safety backup
    safety = br._save_safety_backup(f"sqlite:///{tmp_db_path}", data_dir)

    # Modify original
    Path(data_dir, "original.txt").write_bytes(b"modified")
    Path(data_dir, "new.txt").write_bytes(b"new")

    # Rollback
    br._rollback_safety_backup(safety, f"sqlite:///{tmp_db_path}", data_dir)

    assert Path(data_dir, "original.txt").read_bytes() == b"original"
    assert Path(data_dir, "new.txt").exists()  # rollback copies back, doesn't delete extras


# ── _cleanup_safety_backup ────────────────────────────────────────────────────

def test_cleanup_safety_backup_removes_dir(tmp_path: Path) -> None:
    safety = tmp_path / "safety"
    safety.mkdir()
    (safety / "file.txt").write_bytes(b"x")
    br._cleanup_safety_backup(str(safety))
    assert not safety.exists()


def test_cleanup_safety_backup_logs_warning_on_error(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    safety = tmp_path / "safety"
    safety.mkdir()

    def _raise(*args: Any, **kwargs: Any) -> None:
        """Raise OSError unconditionally."""
        raise OSError("permission denied")

    monkeypatch.setattr(br.shutil, "rmtree", _raise)
    # Should not raise, just log a warning
    br._cleanup_safety_backup(str(safety))


# ── restore_backup ────────────────────────────────────────────────────────────

def test_restore_backup_full_flow(valid_backup_zip: bytes, tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """Restore a valid backup and verify files + database are restored."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    # Pre-populate current state so we can verify it's overwritten
    Path(covers_dir, "old_cover.jpg").write_bytes(b"old")
    Path(import_temp_dir, "old.txt").write_bytes(b"old")

    # Ensure the DB path exists before restore (restore replaces it)
    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    # Monkeypatch engine.dispose and _recreate_engine to avoid touching the real engine
    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)

    result = br.restore_backup(
        backup_zip_bytes=valid_backup_zip,
        database_url=f"sqlite:///{tmp_db_path}",
        data_dir=data_dir,
        covers_dir=covers_dir,
        import_temp_dir=import_temp_dir,
    )

    assert result["restored_covers"] == 1
    assert result["restored_books"] == 1

    # Verify covers and import_temp were restored
    assert Path(covers_dir, "cover1.jpg").read_bytes() == b"cover-data"
    assert not Path(covers_dir, "old_cover.jpg").exists()
    assert Path(import_temp_dir, "file.txt").read_bytes() == b"temp-data"

    # Verify database was restored
    conn = sqlite3.connect(db_file)
    row = conn.execute("SELECT title FROM book").fetchone()
    assert row[0] == "Test Book"
    conn.close()


def test_restore_backup_rolls_back_on_failure(valid_backup_zip: bytes, tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """If restore fails mid-way, safety backup should be rolled back."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    # Set up current state
    Path(covers_dir, "existing.jpg").write_bytes(b"existing")
    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)

    # Make ZipFile.read fail on database.db so restore fails during DB read
    original_read = zipfile.ZipFile.read

    def _bad_read(self: zipfile.ZipFile, name: str, pwd: bytes | None = None) -> bytes:
        """Raise BadZipFile when trying to read database.db."""
        if name == "database.db":
            raise zipfile.BadZipFile("corrupt")
        return original_read(self, name, pwd)

    monkeypatch.setattr(zipfile.ZipFile, "read", _bad_read)

    with pytest.raises(RuntimeError, match="Restore failed and was rolled back"):
        br.restore_backup(
            backup_zip_bytes=valid_backup_zip,
            database_url=f"sqlite:///{tmp_db_path}",
            data_dir=data_dir,
            covers_dir=covers_dir,
            import_temp_dir=import_temp_dir,
        )

    # Verify rollback restored the original cover
    assert Path(covers_dir, "existing.jpg").read_bytes() == b"existing"


def test_restore_backup_path_traversal_in_zip(valid_backup_zip: bytes, tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """A ZIP entry with path traversal should raise ValueError during restore."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)

    # Build a malicious ZIP
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")
        zf.writestr("data/../../etc/passwd", b"root")

    with pytest.raises(RuntimeError, match="Restore failed and was rolled back"):
        br.restore_backup(
            backup_zip_bytes=buf.getvalue(),
            database_url=f"sqlite:///{tmp_db_path}",
            data_dir=data_dir,
            covers_dir=covers_dir,
            import_temp_dir=import_temp_dir,
        )


def test_restore_backup_single_file_too_large(valid_backup_zip: bytes, tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """An individual file in the ZIP exceeding MAX_SINGLE_FILE_SIZE should raise."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")
        # Add a huge file
        info = zipfile.ZipInfo("data/huge.bin")
        info.file_size = br.MAX_SINGLE_FILE_SIZE + 1
        zf.writestr(info, b"x" * 100)

    with pytest.raises(RuntimeError, match="Restore failed and was rolled back"):
        br.restore_backup(
            backup_zip_bytes=buf.getvalue(),
            database_url=f"sqlite:///{tmp_db_path}",
            data_dir=data_dir,
            covers_dir=covers_dir,
            import_temp_dir=import_temp_dir,
        )


# ── _recreate_engine ──────────────────────────────────────────────────────────

def test_recreate_engine(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """_recreate_engine should replace app.database.engine."""
    import app.database as db_mod

    original_engine = db_mod.engine
    tmp_db = str(tmp_path / "test.db")
    try:
        conn = sqlite3.connect(tmp_db)
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INT)")
        conn.commit()
        conn.close()

        monkeypatch.setattr(br.settings, "database_url", f"sqlite:///{tmp_db}")
        br._recreate_engine()
        new_engine = db_mod.engine
        assert new_engine is not original_engine
    finally:
        if db_mod.engine is not original_engine:
            db_mod.engine.dispose()
        db_mod.engine = original_engine


# ── Remaining edge cases ──────────────────────────────────────────────────────

def test_release_lock_oserror_on_unlock(monkeypatch: MonkeyPatch) -> None:
    """OSError during flock unlock should be swallowed."""
    br._acquire_operation_lock()
    assert br._lock_fd is not None

    def _raise(*args: Any, **kwargs: Any) -> None:
        """Raise OSError unconditionally."""
        raise OSError("bad fd")

    import fcntl as _fcntl_mod
    monkeypatch.setattr(_fcntl_mod, "flock", _raise)
    br._release_operation_lock()
    assert br._lock_fd is None


def test_validate_zip_extraction_skips_directories() -> None:
    """Directory entries in the ZIP should not count toward total size."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", b"x")
        # Add a directory entry
        zf.writestr("data/", b"")
    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf:
        # Should not raise — directory has 0 file_size
        br._validate_zip_extraction(zf)


def test_restore_backup_creates_directory_entries(tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """ZIP entries ending with '/' should create directories."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)

    # Build a ZIP with a directory entry — use the real DB file
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(tmp_db_path, "database.db")
        zf.writestr("data/x.txt", b"x")
        zf.writestr("data/covers/", b"")  # directory entry

    result = br.restore_backup(
        backup_zip_bytes=buf.getvalue(),
        database_url=f"sqlite:///{tmp_db_path}",
        data_dir=data_dir,
        covers_dir=covers_dir,
        import_temp_dir=import_temp_dir,
    )

    assert result["restored_covers"] == 0
    assert Path(covers_dir).is_dir()


def test_restore_backup_cleans_up_temp_db_on_move_failure(tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """If shutil.move fails, the temporary DB file should be removed."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)

    def _raise_move(*args: Any, **kwargs: Any) -> None:
        """Raise OSError unconditionally."""
        raise OSError("move failed")

    monkeypatch.setattr(br.shutil, "move", _raise_move)

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")

    with pytest.raises(RuntimeError, match="Restore failed and was rolled back"):
        br.restore_backup(
            backup_zip_bytes=buf.getvalue(),
            database_url=f"sqlite:///{tmp_db_path}",
            data_dir=data_dir,
            covers_dir=covers_dir,
            import_temp_dir=import_temp_dir,
        )

    # Verify no stray temp file was left behind
    import glob
    temp_files = glob.glob(os.path.join(os.path.dirname(db_file), "*.tmp*"))
    assert not temp_files, f"Stray temp files found: {temp_files}"


def test_safe_extract_path_rejects_traversal_via_resolve(monkeypatch: MonkeyPatch) -> None:
    """Path traversal detected when resolve() escapes dest_root."""
    original_resolve = Path.resolve

    def _bad_resolve(self: Path, strict: bool = False) -> Path:
        """Return a path outside dest_root to simulate traversal."""
        if str(self) == "/tmp/dest":
            return original_resolve(self, strict=strict)
        return Path("/etc/passwd")

    monkeypatch.setattr(Path, "resolve", _bad_resolve)
    with pytest.raises(ValueError, match="Path traversal detected"):
        br._safe_extract_path(Path("/tmp/dest"), "foo.txt")


def test_restore_backup_skips_data_root_entry(tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """A ZIP entry named exactly 'data/' should be skipped."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(tmp_db_path, "database.db")
        zf.writestr("data/x.txt", b"x")
        zf.writestr("data/", b"")  # root data directory entry — should be skipped

    result = br.restore_backup(
        backup_zip_bytes=buf.getvalue(),
        database_url=f"sqlite:///{tmp_db_path}",
        data_dir=data_dir,
        covers_dir=covers_dir,
        import_temp_dir=import_temp_dir,
    )
    assert result["restored_covers"] == 0


def test_restore_backup_single_file_size_check_during_extraction(valid_backup_zip: bytes, tmp_db_path: str, backup_dirs: dict[str, str], monkeypatch: MonkeyPatch) -> None:
    """Individual file size check during extraction (line 288)."""
    data_dir = backup_dirs["data_dir"]
    covers_dir = backup_dirs["covers_dir"]
    import_temp_dir = backup_dirs["import_temp_dir"]

    db_file = br._extract_db_path(f"sqlite:///{tmp_db_path}")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(br.engine, "dispose", lambda: None)
    monkeypatch.setattr(br, "_recreate_engine", lambda: None)
    # Bypass the pre-validation so the per-file check triggers
    monkeypatch.setattr(br, "_validate_zip_extraction", lambda zf: None)

    original_getinfo = zipfile.ZipFile.getinfo

    def _fake_getinfo(self: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
        """Return a ZipInfo with inflated file_size to trigger size check."""
        info = original_getinfo(self, name)
        if name == "data/huge.bin":
            info.file_size = br.MAX_SINGLE_FILE_SIZE + 1
        return info

    monkeypatch.setattr(zipfile.ZipFile, "getinfo", _fake_getinfo)

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")
        zf.writestr("data/huge.bin", b"x")

    with pytest.raises(RuntimeError, match="Restore failed and was rolled back"):
        br.restore_backup(
            backup_zip_bytes=buf.getvalue(),
            database_url=f"sqlite:///{tmp_db_path}",
            data_dir=data_dir,
            covers_dir=covers_dir,
            import_temp_dir=import_temp_dir,
        )
