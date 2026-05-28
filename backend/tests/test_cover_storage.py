"""
Unit tests for app.services.cover_storage.download_cover.

All HTTP calls are intercepted with fake clients — no real network I/O.
"""

import hashlib
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from sqlmodel import Session, col, select

from app.services.cover_storage import (
    cleanup_orphan_covers,
    delete_cover_file,
    download_cover,
    resolve_cover_path,
    safe_cover_filename,
    save_uploaded_cover,
)

_VALID_BODY: bytes = b"X" * 10_000
_SMALL_BODY: bytes = b"X" * 100
_IMAGE_URL: str = "https://covers.example.com/book.jpg"
_IMAGE_HEADERS: dict[str, str] = {"content-type": "image/jpeg"}
_PNG_HEADERS: dict[str, str] = {"content-type": "image/png"}
_USER_ID: int = 1


class _FakeCoverResponse:
    """Minimal httpx response stub for cover_storage tests."""

    def __init__(
        self,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.content = body
        self.is_success = 200 <= status_code < 300

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise httpx.HTTPStatusError(
                "error",
                request=None,  # type: ignore[arg-type]
                response=self,  # type: ignore[arg-type]
            )


class _FakeCoverClient:
    """Fake httpx.AsyncClient that maps URLs to pre-built responses."""

    def __init__(self, get_map: dict[str, _FakeCoverResponse] | None = None) -> None:
        self._get = get_map or {}

    async def get(self, url: str, **_kwargs: Any) -> _FakeCoverResponse:
        resp = self._get.get(url)
        if resp is None:
            return _FakeCoverResponse(404)  # pragma: no cover
        return resp


@pytest.mark.anyio
async def test_download_cover_success(tmp_path: Path) -> None:
    """Happy path: valid image is downloaded and saved; filename is returned."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, _IMAGE_HEADERS, _VALID_BODY)}
    )
    filename = await download_cover(_IMAGE_URL, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    assert filename is not None
    assert filename.endswith(".jpg")
    saved = tmp_path / filename
    assert saved.exists()
    assert saved.read_bytes() == _VALID_BODY


@pytest.mark.anyio
async def test_download_cover_dedup(tmp_path: Path) -> None:
    """If the file already exists, it is returned without re-downloading."""
    digest = hashlib.sha256(_IMAGE_URL.encode()).hexdigest()[:32]
    pre_existing = tmp_path / f"{_USER_ID}__{digest}.jpg"
    pre_existing.write_bytes(b"cached")

    client = _FakeCoverClient({})
    filename = await download_cover(_IMAGE_URL, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    assert filename == pre_existing.name


@pytest.mark.anyio
async def test_download_cover_too_small(tmp_path: Path) -> None:
    """Images smaller than 5 KB are rejected and None is returned."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, _IMAGE_HEADERS, _SMALL_BODY)}
    )
    result = await download_cover(_IMAGE_URL, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    assert result is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_download_cover_non_image_content_type(tmp_path: Path) -> None:
    """Responses with non-image content-type are rejected."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, {"content-type": "text/html"}, _VALID_BODY)}
    )
    result = await download_cover(_IMAGE_URL, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    assert result is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_download_cover_http_error(tmp_path: Path) -> None:
    """A 404 (or any non-2xx) response causes None to be returned."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(404, {}, b"")}
    )
    result = await download_cover(_IMAGE_URL, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    assert result is None


@pytest.mark.anyio
async def test_download_cover_network_error(tmp_path: Path) -> None:
    """A network-level exception (e.g. connection refused) returns None."""
    class _ErrorClient:
        async def get(self, url: str, **_kwargs: Any) -> None:
            raise httpx.ConnectError("connection refused")

    result = await download_cover(_IMAGE_URL, tmp_path, _ErrorClient(), _USER_ID)  # type: ignore[arg-type]

    assert result is None


@pytest.mark.anyio
async def test_download_cover_atomic_write(tmp_path: Path) -> None:
    """After a successful download, no leftover .tmp file remains."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, _IMAGE_HEADERS, _VALID_BODY)}
    )
    filename = await download_cover(_IMAGE_URL, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], "Stale .tmp file found after successful download"
    assert (tmp_path / filename).exists()


@pytest.mark.anyio
async def test_download_cover_correct_extension_jpeg(tmp_path: Path) -> None:
    """image/jpeg responses are stored with a .jpg extension."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, {"content-type": "image/jpeg"}, _VALID_BODY)}
    )
    filename = await download_cover(_IMAGE_URL, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    assert filename is not None
    assert filename.endswith(".jpg")


@pytest.mark.anyio
async def test_download_cover_correct_extension_png(tmp_path: Path) -> None:
    """image/png responses are stored with a .png extension."""
    png_url = "https://covers.example.com/book.png"
    client = _FakeCoverClient(
        {png_url: _FakeCoverResponse(200, {"content-type": "image/png"}, _VALID_BODY)}
    )
    filename = await download_cover(png_url, tmp_path, client, _USER_ID)  # type: ignore[arg-type]

    assert filename is not None
    assert filename.endswith(".png")


# ── save_uploaded_cover tests ─────────────────────────────────────────────────


def test_save_uploaded_cover_success(tmp_path: Path) -> None:
    """Valid JPEG bytes are written and filename is returned."""
    body = b"X" * 10_000
    filename = save_uploaded_cover(body, "image/jpeg", tmp_path, _USER_ID)

    assert filename is not None
    assert filename.endswith(".jpg")
    assert (tmp_path / filename).exists()
    assert (tmp_path / filename).read_bytes() == body


def test_save_uploaded_cover_png(tmp_path: Path) -> None:
    """image/png content-type results in a .png filename."""
    body = b"Y" * 10_000
    filename = save_uploaded_cover(body, "image/png", tmp_path, _USER_ID)

    assert filename is not None
    assert filename.endswith(".png")


def test_save_uploaded_cover_too_small(tmp_path: Path) -> None:
    """Images smaller than 5 KB are rejected."""
    body = b"X" * 100
    result = save_uploaded_cover(body, "image/jpeg", tmp_path, _USER_ID)

    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_cover_non_image(tmp_path: Path) -> None:
    """Non-image content-type is rejected."""
    body = b"X" * 10_000
    result = save_uploaded_cover(body, "text/plain", tmp_path, _USER_ID)

    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_cover_dedup(tmp_path: Path) -> None:
    """Uploading the same bytes twice returns the cached filename without rewriting."""
    body = b"Z" * 10_000
    digest = hashlib.sha256(body).hexdigest()[:32]
    pre_existing = tmp_path / f"{_USER_ID}__{digest}.jpg"
    pre_existing.write_bytes(b"original")

    result = save_uploaded_cover(body, "image/jpeg", tmp_path, _USER_ID)

    assert result == pre_existing.name
    assert pre_existing.read_bytes() == b"original"


def test_save_uploaded_cover_no_tmp_leftover(tmp_path: Path) -> None:
    """No stale .tmp file remains after a successful save."""
    body = b"X" * 10_000
    filename = save_uploaded_cover(body, "image/jpeg", tmp_path, _USER_ID)

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []
    assert filename is not None
    assert (tmp_path / filename).exists()


def test_safe_cover_filename_empty() -> None:
    """Empty or None filename should be rejected."""
    assert safe_cover_filename("") is None
    assert safe_cover_filename(None) is None


def test_resolve_cover_path_none() -> None:
    """None or empty filename should return None."""
    assert resolve_cover_path("/tmp/covers", None) is None
    assert resolve_cover_path("/tmp/covers", "") is None


def test_delete_cover_file_invalid_filename() -> None:
    """Invalid filename should return False without touching filesystem."""
    assert delete_cover_file("", "/tmp/covers") is False
    assert delete_cover_file(None, "/tmp/covers") is False  # type: ignore[arg-type]


def test_delete_cover_file_unlink_error(monkeypatch) -> None:
    """OSError during unlink should return False."""
    mock_path = MagicMock()
    mock_path.unlink.side_effect = OSError("permission denied")
    monkeypatch.setattr(
        "app.services.cover_storage.resolve_cover_path", lambda d, f: mock_path
    )
    assert delete_cover_file("test.jpg", "/tmp/covers") is False


@pytest.mark.anyio
async def test_download_cover_oserror_on_write(tmp_path: Path, monkeypatch) -> None:
    """OSError during atomic write should return None."""
    class _FakeResponse:
        status_code = 200
        headers = {"content-type": "image/jpeg"}
        content = b"X" * 10_000
        is_success = True

        def raise_for_status(self) -> None:
            pass

    class _FakeClient:
        async def get(self, url: str, **_kwargs: Any) -> _FakeResponse:
            return _FakeResponse()

    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.services.cover_storage.Path.mkdir", _raise)
    result = await download_cover(
        "https://example.com/img.jpg", tmp_path, _FakeClient(), 1
    )
    assert result is None


def test_save_uploaded_cover_oserror_on_write(tmp_path: Path, monkeypatch) -> None:
    """OSError during atomic write should return None."""
    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.services.cover_storage.Path.mkdir", _raise)
    body = b"X" * 10_000
    result = save_uploaded_cover(body, "image/jpeg", tmp_path, 1)
    assert result is None


def test_save_uploaded_cover_content_type_with_params(tmp_path: Path) -> None:
    """Content-type with charset suffix is handled (e.g. 'image/jpeg; charset=...')."""
    body = b"X" * 10_000
    filename = save_uploaded_cover(body, "image/jpeg; charset=utf-8", tmp_path, _USER_ID)

    assert filename is not None
    assert filename.endswith(".jpg")


def test_cleanup_orphan_covers_deletes_unreferenced_files(session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover files on disk that are not referenced by any book should be deleted."""
    from app.models import Book
    from app.services import cover_storage
    import time

    # Create a book with a local cover URL
    book = Book(user_id=1, title="Test", cover_url="/api/covers/1__abc123.jpg")
    session.add(book)
    session.commit()

    # Verify the book is in the database
    result = session.exec(select(Book.cover_url).where(col(Book.cover_url).is_not(None))).all()
    assert len(result) == 1
    assert result[0] == "/api/covers/1__abc123.jpg"

    # Create cover files on disk
    (tmp_path / "1__abc123.jpg").write_bytes(b"referenced")
    (tmp_path / "1__orphan1.jpg").write_bytes(b"orphan1")
    (tmp_path / "1__orphan2.png").write_bytes(b"orphan2")

    # Make orphan files old enough to be eligible for deletion
    old_time = time.time() - 7200  # 2 hours ago
    os.utime(tmp_path / "1__orphan1.jpg", (old_time, old_time))
    os.utime(tmp_path / "1__orphan2.png", (old_time, old_time))

    monkeypatch.setattr(cover_storage.settings, "covers_dir", str(tmp_path))

    deleted = cleanup_orphan_covers(session)
    assert deleted == 2
    assert (tmp_path / "1__abc123.jpg").exists()
    assert not (tmp_path / "1__orphan1.jpg").exists()
    assert not (tmp_path / "1__orphan2.png").exists()


def test_cleanup_orphan_covers_skips_recent_files(session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Recently modified orphan files should not be deleted."""
    from app.services import cover_storage

    (tmp_path / "1__recent.jpg").write_bytes(b"recent")

    monkeypatch.setattr(cover_storage.settings, "covers_dir", str(tmp_path))

    deleted = cleanup_orphan_covers(session)
    assert deleted == 0
    assert (tmp_path / "1__recent.jpg").exists()


def test_cleanup_orphan_covers_empty_dir(session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty covers directory should return 0."""
    from app.services import cover_storage

    monkeypatch.setattr(cover_storage.settings, "covers_dir", str(tmp_path))

    assert cleanup_orphan_covers(session) == 0


def test_cleanup_orphan_covers_nonexistent_dir(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nonexistent covers directory should return 0."""
    from app.services import cover_storage

    monkeypatch.setattr(cover_storage.settings, "covers_dir", "/nonexistent/path")

    assert cleanup_orphan_covers(session) == 0
