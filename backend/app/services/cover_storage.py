"""
Local cover image storage service.

Downloads cover images from external URLs, stores them on disk with an atomic
write, and returns the local filename.  Callers fall back to the original URL
when this module returns ``None``.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import text
from sqlmodel import Session, col, select

from app.config import settings
from app.models import Book

logger = logging.getLogger(__name__)

_MIN_COVER_BYTES: int = 1_000

_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


async def download_cover(
    url: str,
    covers_dir: str | Path,
    client: httpx.AsyncClient,
    user_id: int,
) -> str | None:
    """Download a cover image and persist it locally.

    Args:
        url: External URL of the cover image.
        covers_dir: Directory where cover files are stored.
        client: An httpx.AsyncClient to use for the download.

    Returns:
        The local filename (e.g. ``"abc123def456.jpg"``) on success, or
        None if the download failed or the image did not pass validation.
    """
    covers_path = Path(covers_dir)

    digest = hashlib.sha256(url.encode()).hexdigest()[:32]
    prefix = f"{user_id}__"

    # Deduplication: if any file with this digest already exists, skip download.
    existing = list(covers_path.glob(f"{prefix}{digest}.*"))
    if existing:
        logger.debug("Cover already cached: %s", existing[0].name)
        return existing[0].name

    try:
        resp = await client.get(url)
        resp.raise_for_status()
        body = resp.content
    except Exception as exc:
        logger.warning("Cover download failed for %s: %s", url, exc)
        return None

    if len(body) < _MIN_COVER_BYTES:
        logger.warning("Cover too small (%d bytes) for %s — skipping", len(body), url)
        return None

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    if not content_type.startswith("image/"):
        logger.warning(
            "Cover content-type not an image (%s) for %s — skipping",
            content_type,
            url,
        )
        return None

    ext = _CONTENT_TYPE_TO_EXT.get(content_type, ".jpg")
    filename = f"{prefix}{digest}{ext}"
    tmp_path = covers_path / f"{filename}.tmp"
    final_path = covers_path / filename

    try:
        covers_path.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(body)
        os.replace(tmp_path, final_path)
    except OSError as exc:
        logger.error("Failed to write cover %s: %s", filename, exc)
        return None

    logger.debug("Cover saved: %s (%d bytes)", filename, len(body))
    return filename


def local_cover_filename(cover_url: str | None) -> str | None:
    """Extract a local cover filename from a stored ``/api/covers/...`` URL.

    Args:
        cover_url: A URL path like ``/api/covers/abc123.jpg`` or None.

    Returns:
        The filename portion (e.g. ``"abc123.jpg"``) or None if the URL does
        not match the expected pattern.
    """
    if not cover_url or not cover_url.startswith("/api/covers/"):
        return None

    return safe_cover_filename(cover_url.removeprefix("/api/covers/"))


def safe_cover_filename(filename: str | None) -> str | None:
    """Validate a cover filename and reject path traversal attempts.

    Args:
        filename: A candidate filename or None.

    Returns:
        The filename if safe, or None if it contains path separators or
        parent directory references.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    return filename


def resolve_cover_path(covers_dir: str | Path, filename: str | None) -> Path | None:
    """Return the absolute path for a safe cover filename.

    Args:
        covers_dir: Directory where cover files are stored.
        filename: A candidate filename or None.

    Returns:
        An absolute Path if the filename is safe, or None otherwise.
    """
    safe_filename = safe_cover_filename(filename)
    if not safe_filename:
        return None
    return Path(covers_dir) / safe_filename


def save_uploaded_cover(
    body: bytes,
    content_type: str,
    covers_dir: str | Path,
    user_id: int,
) -> str | None:
    """Persist an uploaded cover image locally.

    Args:
        body: Raw image bytes from the upload.
        content_type: MIME type declared by the client (e.g. ``"image/jpeg"``).
        covers_dir: Directory where cover files are stored.

    Returns:
        The local filename on success, or None if validation failed.
    """
    ct = content_type.split(";")[0].strip()
    if not ct.startswith("image/"):
        logger.warning("Uploaded cover not an image: %s", ct)
        return None

    if len(body) < _MIN_COVER_BYTES:
        logger.warning("Uploaded cover too small: %d bytes", len(body))
        return None

    covers_path = Path(covers_dir)
    digest = hashlib.sha256(body).hexdigest()[:32]
    prefix = f"{user_id}__"

    # Deduplication: if any file with this digest already exists, skip write.
    existing = list(covers_path.glob(f"{prefix}{digest}.*"))
    if existing:
        logger.debug("Uploaded cover already cached: %s", existing[0].name)
        return existing[0].name

    ext = _CONTENT_TYPE_TO_EXT.get(ct, ".jpg")
    filename = f"{prefix}{digest}{ext}"
    tmp_path = covers_path / f"{filename}.tmp"
    final_path = covers_path / filename

    try:
        covers_path.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(body)
        os.replace(tmp_path, final_path)
    except OSError as exc:
        logger.error("Failed to write uploaded cover %s: %s", filename, exc)
        return None

    logger.debug("Uploaded cover saved: %s (%d bytes)", filename, len(body))
    return filename


def delete_cover_file(filename: str, covers_dir: str | Path) -> bool:
    """Delete a cached cover file if it exists.

    Args:
        filename: The cover filename to delete.
        covers_dir: Directory where cover files are stored.

    Returns:
        True if the file was deleted or did not exist, False on error.
    """
    path = resolve_cover_path(covers_dir, filename)
    if path is None:
        return False

    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to delete cover %s: %s", filename, exc)
        return False

    logger.debug("Deleted cover: %s", filename)
    return True


def cleanup_orphan_covers(session: Session, grace_minutes: int = 60) -> int:
    """Delete cover files on disk that are no longer referenced by any book.

    Only files older than *grace_minutes* are considered for deletion, to
    avoid removing covers that were just uploaded but not yet saved to the
    book entry.

    Args:
        session: Database session for querying book cover URLs.
        grace_minutes: Minimum age in minutes before an orphaned file is
            eligible for deletion. Defaults to 60.

    Returns:
        Number of orphaned files deleted.
    """
    import time

    covers_path = Path(settings.covers_dir)
    if not covers_path.exists():
        return 0

    referenced = {
        url.removeprefix("/api/covers/")
        for url in session.exec(select(Book.cover_url).where(col(Book.cover_url).is_not(None))).all()
        if url and url.startswith("/api/covers/")
    }

    cutoff = time.time() - (grace_minutes * 60)
    deleted = 0
    for filename in covers_path.iterdir():
        if filename.is_file() and filename.name not in referenced:
            try:
                if filename.stat().st_mtime > cutoff:
                    logger.debug("Skipping recently modified cover: %s", filename.name)
                    continue
                filename.unlink()
                logger.info("Deleted orphaned cover: %s", filename.name)
                deleted += 1
            except OSError as exc:
                logger.warning("Failed to delete orphaned cover %s: %s", filename.name, exc)

    return deleted
