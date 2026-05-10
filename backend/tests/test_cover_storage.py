"""
Unit tests for app.services.cover_storage.download_cover.

All HTTP calls are intercepted with fake clients — no real network I/O.
"""

import pytest

from app.services.cover_storage import download_cover, save_uploaded_cover

# ── Fake HTTP infrastructure ──────────────────────────────────────────────────

_VALID_BODY = b"X" * 10_000  # 10 KB — well above the 5 KB minimum
_SMALL_BODY = b"X" * 100    # 100 bytes — below the 5 KB minimum


class _FakeCoverResponse:
    """Minimal httpx response stub for cover_storage tests."""

    def __init__(
        self,
        status_code: int = 200,
        headers: dict | None = None,
        body: bytes = b"",
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = body
        self.is_success = 200 <= status_code < 300

    def raise_for_status(self):
        if not self.is_success:
            import httpx
            raise httpx.HTTPStatusError(
                "error",
                request=None,  # type: ignore[arg-type]
                response=self,  # type: ignore[arg-type]
            )


class _FakeCoverClient:
    """Fake httpx.AsyncClient that maps URLs to pre-built responses."""

    def __init__(self, get_map: dict | None = None):
        self._get = get_map or {}

    async def get(self, url: str, **_kwargs) -> _FakeCoverResponse:
        resp = self._get.get(url)
        if resp is None:
            return _FakeCoverResponse(404)
        return resp


_IMAGE_URL = "https://covers.example.com/book.jpg"
_IMAGE_HEADERS = {"content-type": "image/jpeg"}
_PNG_HEADERS = {"content-type": "image/png"}


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_download_cover_success(tmp_path):
    """Happy path: valid image is downloaded and saved; filename is returned."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, _IMAGE_HEADERS, _VALID_BODY)}
    )
    filename = await download_cover(_IMAGE_URL, tmp_path, client)  # type: ignore[arg-type]

    assert filename is not None
    assert filename.endswith(".jpg")
    saved = tmp_path / filename
    assert saved.exists()
    assert saved.read_bytes() == _VALID_BODY


@pytest.mark.anyio
async def test_download_cover_dedup(tmp_path):
    """If the file already exists, it is returned without re-downloading."""
    # Pre-create a file with the expected digest prefix.
    import hashlib
    digest = hashlib.sha256(_IMAGE_URL.encode()).hexdigest()[:32]
    pre_existing = tmp_path / f"{digest}.jpg"
    pre_existing.write_bytes(b"cached")

    # Client returns nothing — dedup path must not call it.
    client = _FakeCoverClient({})
    filename = await download_cover(_IMAGE_URL, tmp_path, client)  # type: ignore[arg-type]

    assert filename == pre_existing.name


@pytest.mark.anyio
async def test_download_cover_too_small(tmp_path):
    """Images smaller than 5 KB are rejected and None is returned."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, _IMAGE_HEADERS, _SMALL_BODY)}
    )
    result = await download_cover(_IMAGE_URL, tmp_path, client)  # type: ignore[arg-type]

    assert result is None
    # No files should have been written.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_download_cover_non_image_content_type(tmp_path):
    """Responses with non-image content-type are rejected."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, {"content-type": "text/html"}, _VALID_BODY)}
    )
    result = await download_cover(_IMAGE_URL, tmp_path, client)  # type: ignore[arg-type]

    assert result is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_download_cover_http_error(tmp_path):
    """A 404 (or any non-2xx) response causes None to be returned."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(404, {}, b"")}
    )
    result = await download_cover(_IMAGE_URL, tmp_path, client)  # type: ignore[arg-type]

    assert result is None


@pytest.mark.anyio
async def test_download_cover_network_error(tmp_path):
    """A network-level exception (e.g. connection refused) returns None."""
    import httpx

    class _ErrorClient:
        async def get(self, url: str, **_kwargs):
            raise httpx.ConnectError("connection refused")

    result = await download_cover(_IMAGE_URL, tmp_path, _ErrorClient())  # type: ignore[arg-type]

    assert result is None


@pytest.mark.anyio
async def test_download_cover_atomic_write(tmp_path):
    """After a successful download, no leftover .tmp file remains."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, _IMAGE_HEADERS, _VALID_BODY)}
    )
    filename = await download_cover(_IMAGE_URL, tmp_path, client)  # type: ignore[arg-type]

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], "Stale .tmp file found after successful download"
    assert (tmp_path / filename).exists()


@pytest.mark.anyio
async def test_download_cover_correct_extension_jpeg(tmp_path):
    """image/jpeg responses are stored with a .jpg extension."""
    client = _FakeCoverClient(
        {_IMAGE_URL: _FakeCoverResponse(200, {"content-type": "image/jpeg"}, _VALID_BODY)}
    )
    filename = await download_cover(_IMAGE_URL, tmp_path, client)  # type: ignore[arg-type]

    assert filename is not None
    assert filename.endswith(".jpg")


@pytest.mark.anyio
async def test_download_cover_correct_extension_png(tmp_path):
    """image/png responses are stored with a .png extension."""
    png_url = "https://covers.example.com/book.png"
    client = _FakeCoverClient(
        {png_url: _FakeCoverResponse(200, {"content-type": "image/png"}, _VALID_BODY)}
    )
    filename = await download_cover(png_url, tmp_path, client)  # type: ignore[arg-type]

    assert filename is not None
    assert filename.endswith(".png")


# ── save_uploaded_cover tests ─────────────────────────────────────────────────

def test_save_uploaded_cover_success(tmp_path):
    """Valid JPEG bytes are written and filename is returned."""
    body = b"X" * 10_000  # 10 KB
    filename = save_uploaded_cover(body, "image/jpeg", tmp_path)

    assert filename is not None
    assert filename.endswith(".jpg")
    assert (tmp_path / filename).exists()
    assert (tmp_path / filename).read_bytes() == body


def test_save_uploaded_cover_png(tmp_path):
    """image/png content-type results in a .png filename."""
    body = b"Y" * 10_000
    filename = save_uploaded_cover(body, "image/png", tmp_path)

    assert filename is not None
    assert filename.endswith(".png")


def test_save_uploaded_cover_too_small(tmp_path):
    """Images smaller than 5 KB are rejected."""
    body = b"X" * 100
    result = save_uploaded_cover(body, "image/jpeg", tmp_path)

    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_cover_non_image(tmp_path):
    """Non-image content-type is rejected."""
    body = b"X" * 10_000
    result = save_uploaded_cover(body, "text/plain", tmp_path)

    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_cover_dedup(tmp_path):
    """Uploading the same bytes twice returns the cached filename without rewriting."""
    import hashlib

    body = b"Z" * 10_000
    digest = hashlib.sha256(body).hexdigest()[:32]
    pre_existing = tmp_path / f"{digest}.jpg"
    pre_existing.write_bytes(b"original")

    result = save_uploaded_cover(body, "image/jpeg", tmp_path)

    assert result == pre_existing.name
    # Original file must NOT be overwritten.
    assert pre_existing.read_bytes() == b"original"


def test_save_uploaded_cover_no_tmp_leftover(tmp_path):
    """No stale .tmp file remains after a successful save."""
    body = b"X" * 10_000
    filename = save_uploaded_cover(body, "image/jpeg", tmp_path)

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []
    assert filename is not None
    assert (tmp_path / filename).exists()


def test_save_uploaded_cover_content_type_with_params(tmp_path):
    """Content-type with charset suffix is handled (e.g. 'image/jpeg; charset=...')."""
    body = b"X" * 10_000
    filename = save_uploaded_cover(body, "image/jpeg; charset=utf-8", tmp_path)

    assert filename is not None
    assert filename.endswith(".jpg")
