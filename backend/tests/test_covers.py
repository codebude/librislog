"""
Endpoint tests for GET /api/covers/{filename} and POST /api/covers/upload.

Uses a dedicated fixture that monkeypatches settings.covers_dir to a
temporary directory so tests never touch the real filesystem.
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.auth import require_user_by_api_key
from app.config import settings
from app.main import app
from app.models import User, UserRole


@pytest.fixture()
def covers_client(tmp_path, monkeypatch):
    """TestClient with covers_dir pointed at a fresh tmp directory."""
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path))

    def _fake_user() -> User:
        return User(id=1, firstname="Test", lastname="User", email="test@example.com", role=UserRole.user, hashed_password="x")

    app.dependency_overrides[require_user_by_api_key] = _fake_user
    with TestClient(app) as client:
        yield client, tmp_path
    app.dependency_overrides.clear()


# ── GET /api/covers/{filename} ─────────────────────────────────────────────────

def test_get_cover_serves_file(covers_client):
    """A file placed in covers_dir is served with HTTP 200."""
    client, covers_dir = covers_client
    filename = "abc123.jpg"
    (covers_dir / filename).write_bytes(b"fake-image-data")

    resp = client.get(f"/api/covers/{filename}")
    assert resp.status_code == 200
    assert resp.content == b"fake-image-data"


def test_get_cover_404_for_missing(covers_client):
    """Requesting a file that does not exist returns HTTP 404."""
    client, _ = covers_client
    resp = client.get("/api/covers/nonexistent.jpg")
    assert resp.status_code == 404


# ── POST /api/covers/upload ────────────────────────────────────────────────────

_VALID_IMAGE = b"I" * 10_000  # 10 KB — passes the 5 KB minimum


def test_upload_cover_valid_jpeg(covers_client):
    """A valid JPEG upload returns 200 and a local cover_url."""
    client, covers_dir = covers_client
    resp = client.post(
        "/api/covers/upload",
        files={"file": ("cover.jpg", io.BytesIO(_VALID_IMAGE), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "cover_url" in data
    assert data["cover_url"].startswith("/api/covers/")
    filename = data["cover_url"].removeprefix("/api/covers/")
    assert (covers_dir / filename).exists()


def test_upload_cover_valid_png(covers_client):
    """A valid PNG upload returns 200 and a .png filename."""
    client, covers_dir = covers_client
    resp = client.post(
        "/api/covers/upload",
        files={"file": ("cover.png", io.BytesIO(_VALID_IMAGE), "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    filename = data["cover_url"].removeprefix("/api/covers/")
    assert filename.endswith(".png")


def test_upload_cover_too_small_returns_422(covers_client):
    """Images smaller than 5 KB are rejected with HTTP 422."""
    client, _ = covers_client
    small = b"X" * 100
    resp = client.post(
        "/api/covers/upload",
        files={"file": ("tiny.jpg", io.BytesIO(small), "image/jpeg")},
    )
    assert resp.status_code == 422


def test_upload_cover_non_image_returns_422(covers_client):
    """A non-image content-type is rejected with HTTP 422."""
    client, _ = covers_client
    resp = client.post(
        "/api/covers/upload",
        files={"file": ("data.txt", io.BytesIO(_VALID_IMAGE), "text/plain")},
    )
    assert resp.status_code == 422


def test_upload_cover_dedup_returns_same_url(covers_client):
    """Uploading the same bytes twice returns the same cover_url."""
    client, _ = covers_client
    make = lambda: client.post(  # noqa: E731
        "/api/covers/upload",
        files={"file": ("cover.jpg", io.BytesIO(_VALID_IMAGE), "image/jpeg")},
    )
    r1 = make()
    r2 = make()
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["cover_url"] == r2.json()["cover_url"]
