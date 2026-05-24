"""Integration tests for admin backup/restore endpoints.

These tests run the full FastAPI stack and exercise the real backup/restore
service.  Each test uses its own file-based SQLite database so that restore
operations (which overwrite the DB file) cannot interfere with other tests.
"""

import io
import json
import sqlite3
import zipfile
from collections.abc import Generator
from pathlib import Path
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth import encrypt_api_key, generate_api_key, get_api_key_prefix, get_password_hash, hash_api_key
from app.config import settings
from app.database import engine as real_engine, get_session
from app.main import app
from app.models import ApiKey, Book, User, UserRole, UserSettings
from app.services import backup_restore as br


@pytest.fixture()
def admin_client_with_file_db(tmp_path: Path, monkeypatch: MonkeyPatch) -> Generator[tuple[TestClient, str], None, None]:
    """Yield a TestClient backed by a real file-based SQLite DB."""
    db_path = tmp_path / "admin_test.db"
    data_dir = tmp_path / "data"
    covers_dir = tmp_path / "covers"
    import_temp_dir = tmp_path / "import_temp"
    backup_temp_dir = tmp_path / "backup_temp"

    for d in (data_dir, covers_dir, import_temp_dir, backup_temp_dir):
        d.mkdir(parents=True, exist_ok=True)

    file_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(file_engine)

    with Session(file_engine) as session:
        user = User(
            firstname="Admin",
            lastname="User",
            email="admin@example.com",
            role=UserRole.admin,
            hashed_password=get_password_hash("admin-pass"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        session.add(UserSettings(user_id=user.id, language="en"))

        key_plain = generate_api_key()
        session.add(
            ApiKey(
                user_id=user.id,
                key_prefix=get_api_key_prefix(key_plain),
                key_hash=hash_api_key(key_plain),
                key_encrypted=encrypt_api_key(key_plain),
                description="Admin key",
            )
        )
        session.commit()

        # Seed a book so the DB is non-empty
        book = Book(
            user_id=user.id,
            title="Original Book",
            reading_status="want_to_read",
        )
        session.add(book)
        session.commit()

    # Override settings to point at our temp directories
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "data_dir", str(data_dir))
    monkeypatch.setattr(settings, "covers_dir", str(covers_dir))
    monkeypatch.setattr(settings, "import_temp_dir", str(import_temp_dir))
    monkeypatch.setattr(settings, "backup_temp_dir", str(backup_temp_dir))

    def override_get_session() -> Generator[Session, None, None]:
        with Session(file_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    # Snapshot the real engine so we can restore it after restore_backup
    original_engine = real_engine

    with TestClient(app) as client:
        client.headers["X-API-Key"] = key_plain
        yield client, str(db_path)

    # Cleanup
    app.dependency_overrides.clear()
    import app.database as db_mod
    # restore_backup calls _recreate_engine() which creates a new engine.
    # Dispose it before restoring the original so we don't leak connections.
    if db_mod.engine is not original_engine:
        db_mod.engine.dispose()
    db_mod.engine = original_engine
    file_engine.dispose()
    br._release_operation_lock()


# ── Backup endpoint ───────────────────────────────────────────────────────────

def test_admin_backup_download_success(admin_client_with_file_db: tuple[TestClient, str]) -> None:
    client, db_path = admin_client_with_file_db

    # Add a cover file so the backup contains data
    cover = Path(settings.covers_dir) / "cover1.jpg"
    cover.write_bytes(b"cover-data")

    resp = client.get("/api/admin/backup")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "librislog-backup" in resp.headers["content-disposition"]

    data = resp.content
    assert len(data) > 0

    # Verify it's a valid ZIP with the expected entries
    import io
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        names = zf.namelist()
        assert "database.db" in names
        assert "metadata.json" in names
        assert "data/covers/cover1.jpg" in names

        meta = json.loads(zf.read("metadata.json"))
        assert meta["app_version"] is not None
        assert meta["covers_count"] == 1


def test_admin_backup_download_concurrent_lock(admin_client_with_file_db: tuple[TestClient, str], monkeypatch: MonkeyPatch) -> None:
    client, _ = admin_client_with_file_db

    # Hold the lock manually
    br._acquire_operation_lock()
    try:
        resp = client.get("/api/admin/backup")
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]
    finally:
        br._release_operation_lock()


# ── Validate-backup endpoint ──────────────────────────────────────────────────

def test_admin_validate_backup_success(admin_client_with_file_db: tuple[TestClient, str]) -> None:
    client, _ = admin_client_with_file_db

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")
        zf.writestr("metadata.json", json.dumps({"v": "1"}))

    resp = client.post(
        "/api/admin/validate-backup",
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["metadata"]["v"] == "1"


def test_admin_validate_backup_missing_database(admin_client_with_file_db: tuple[TestClient, str]) -> None:
    client, _ = admin_client_with_file_db

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/x.txt", b"x")
        zf.writestr("metadata.json", b"{}")

    resp = client.post(
        "/api/admin/validate-backup",
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "missing database.db" in resp.json()["detail"]


# ── Restore endpoint ──────────────────────────────────────────────────────────

def test_admin_restore_success(admin_client_with_file_db: tuple[TestClient, str]) -> None:
    """Full round-trip: backup -> modify DB -> restore -> verify original state."""
    client, db_path = admin_client_with_file_db

    # Add a cover file so the backup contains a data/ directory
    cover = Path(settings.covers_dir) / "cover1.jpg"
    cover.write_bytes(b"cover-data")

    # 1. Create a backup
    backup_resp = client.get("/api/admin/backup")
    assert backup_resp.status_code == 200
    backup_bytes = backup_resp.content

    # 2. Modify the database (add a new book)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO book (title, author, page_count, user_id, reading_status) VALUES ('New Book', '', 0, 1, 'read')")
    conn.commit()
    row = conn.execute("SELECT COUNT(*) FROM book").fetchone()
    assert row[0] == 2
    conn.close()

    # 3. Restore from backup
    restore_resp = client.post(
        "/api/admin/restore",
        files={"file": ("backup.zip", backup_bytes, "application/zip")},
    )
    assert restore_resp.status_code == 200
    result = restore_resp.json()
    assert result["restored_books"] == 1  # original seed book

    # 4. Verify database is back to original state (1 book)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT COUNT(*) FROM book").fetchone()
    assert row[0] == 1
    title = conn.execute("SELECT title FROM book").fetchone()[0]
    assert title == "Original Book"
    conn.close()


def test_admin_restore_invalid_backup(admin_client_with_file_db: tuple[TestClient, str]) -> None:
    client, _ = admin_client_with_file_db

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/x.txt", b"x")

    resp = client.post(
        "/api/admin/restore",
        files={"file": ("bad.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "missing database.db" in resp.json()["detail"]


def test_admin_restore_requires_admin(client: TestClient, create_user_with_key: Callable[..., tuple[User, str]]) -> None:
    """Non-admin users should get 403 on restore."""
    user, key = create_user_with_key(email="user@example.com", role=UserRole.user)
    client.headers["X-API-Key"] = key

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("database.db", b"db")
        zf.writestr("data/x.txt", b"x")

    resp = client.post(
        "/api/admin/restore",
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 403


# ── Unit tests for uncovered error branches ───────────────────────────────────

def test_admin_backup_download_runtime_error(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    import app.routers.admin as admin_module

    def fake_create_backup(**kwargs: Any) -> bytes:
        raise RuntimeError("disk full")

    monkeypatch.setattr(admin_module, "create_backup", fake_create_backup)

    resp = client.get("/api/admin/backup")
    assert resp.status_code == 500
    assert "Backup failed" in resp.json()["detail"]


def test_admin_backup_download_generic_exception(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    import app.routers.admin as admin_module

    def fake_create_backup(**kwargs: Any) -> bytes:
        raise Exception("boom")

    monkeypatch.setattr(admin_module, "create_backup", fake_create_backup)

    resp = client.get("/api/admin/backup")
    assert resp.status_code == 500
    assert "Backup failed" in resp.json()["detail"]


def test_admin_validate_backup_value_error(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    import app.routers.admin as admin_module

    def fake_validate(contents: bytes) -> dict[str, Any]:
        raise ValueError("bad zip")

    monkeypatch.setattr(admin_module, "validate_backup_zip", fake_validate)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("x.txt", b"x")

    resp = client.post(
        "/api/admin/validate-backup",
        files={"file": ("backup.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "bad zip" in resp.json()["detail"]


def test_admin_restore_validate_value_error(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    import app.routers.admin as admin_module

    def fake_validate(contents: bytes) -> dict[str, Any]:
        raise ValueError("bad zip")

    monkeypatch.setattr(admin_module, "validate_backup_zip", fake_validate)

    resp = client.post(
        "/api/admin/restore",
        files={"file": ("bad.zip", b"x", "application/zip")},
    )
    assert resp.status_code == 400
    assert "bad zip" in resp.json()["detail"]


def test_admin_restore_runtime_error(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    import app.routers.admin as admin_module

    def fake_validate(contents: bytes) -> dict[str, Any]:
        return {"valid": True}

    def fake_restore(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("disk full")

    monkeypatch.setattr(admin_module, "validate_backup_zip", fake_validate)
    monkeypatch.setattr(admin_module, "restore_backup", fake_restore)

    resp = client.post(
        "/api/admin/restore",
        files={"file": ("backup.zip", b"x", "application/zip")},
    )
    assert resp.status_code == 500
    assert "disk full" in resp.json()["detail"]


def test_admin_restore_generic_exception(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    import app.routers.admin as admin_module

    def fake_validate(contents: bytes) -> dict[str, Any]:
        return {"valid": True}

    def fake_restore(**kwargs: Any) -> dict[str, Any]:
        raise Exception("boom")

    monkeypatch.setattr(admin_module, "validate_backup_zip", fake_validate)
    monkeypatch.setattr(admin_module, "restore_backup", fake_restore)

    resp = client.post(
        "/api/admin/restore",
        files={"file": ("backup.zip", b"x", "application/zip")},
    )
    assert resp.status_code == 500
    assert "Restore failed" in resp.json()["detail"]


def test_admin_restore_concurrent_lock(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    import app.routers.admin as admin_module

    def fake_validate(contents: bytes) -> dict[str, Any]:
        return {"valid": True}

    def fake_restore(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("already in progress")

    monkeypatch.setattr(admin_module, "validate_backup_zip", fake_validate)
    monkeypatch.setattr(admin_module, "restore_backup", fake_restore)

    resp = client.post(
        "/api/admin/restore",
        files={"file": ("backup.zip", b"x", "application/zip")},
    )
    assert resp.status_code == 409
    assert "already in progress" in resp.json()["detail"]
