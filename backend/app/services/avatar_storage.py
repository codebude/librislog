"""Local avatar image storage and normalisation.

Avatars are decoded with Pillow, normalised to a square WebP file, and written
atomically to ``settings.avatars_dir``. The database row lives in
``app.services.avatar``.
"""

import hashlib
import io
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.models import UserImage
from app.services.cover_import import is_safe_cover_import_url

logger = logging.getLogger(__name__)

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}
_MAX_PICTURE_URL_LENGTH = 2048
# Hard cap before decoding. Pillow raises above twice this value.
_MAX_IMAGE_PIXELS = 40_000_000


@dataclass
class StoredAvatar:
    """Metadata for a normalised avatar file on disk."""

    filename: str
    content_type: str
    byte_size: int


def safe_avatar_filename(filename: str | None) -> str | None:
    """Validate an avatar filename and reject path traversal attempts."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    return filename


def resolve_avatar_path(filename: str | None, avatars_dir: str | Path) -> Path | None:
    """Return the absolute path for a safe avatar filename."""
    safe_filename = safe_avatar_filename(filename)
    if not safe_filename:
        return None
    return Path(avatars_dir) / safe_filename


def delete_avatar_file(filename: str, avatars_dir: str | Path) -> bool:
    """Delete an avatar file if it exists."""
    path = resolve_avatar_path(filename, avatars_dir)
    if path is None:
        return False

    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to delete avatar %s: %s", filename, exc)
        return False

    logger.debug("Deleted avatar: %s", filename)
    return True


def _normalise_image(body: bytes) -> tuple[bytes, int] | None:
    """Decode, crop, resize, and encode an image as WebP.

    Returns ``(webp_bytes, byte_size)`` or ``None`` when the bytes are not a
    supported, decodable image.
    """
    if not body:
        return None

    Image.MAX_IMAGE_PIXELS = _MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(body)) as source:
            if source.format not in _ALLOWED_PIL_FORMATS:
                logger.warning("Unsupported avatar image format: %s", source.format)
                return None

            if source.width * source.height > _MAX_IMAGE_PIXELS:
                logger.warning(
                    "Avatar image is too large to decode: %dx%d",
                    source.width,
                    source.height,
                )
                return None

            image = ImageOps.exif_transpose(source)
            image.load()

            if image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            ):
                image = image.convert("RGBA")
            else:
                image = image.convert("RGB")

            width, height = image.size
            if width <= 0 or height <= 0:
                return None

            edge = min(width, height)
            left = (width - edge) // 2
            top = (height - edge) // 2
            image = image.crop((left, top, left + edge, top + edge))

            max_dimension = max(1, settings.avatar_max_dimension)
            if image.width > max_dimension or image.height > max_dimension:
                image = image.resize(
                    (max_dimension, max_dimension),
                    Image.Resampling.LANCZOS,
                )

            output = io.BytesIO()
            image.save(
                output,
                format="WEBP",
                quality=max(1, min(100, settings.avatar_quality)),
                method=6,
            )
            encoded = output.getvalue()
            if not encoded:
                return None
            return encoded, len(encoded)
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        logger.warning("Avatar image could not be decoded: %s", exc)
        return None


def _write_atomic(avatars_dir: str | Path, filename: str, body: bytes) -> bool:
    """Write *body* to *filename* atomically inside *avatars_dir*."""
    avatars_path = Path(avatars_dir)
    tmp_path = avatars_path / f"{filename}.tmp"
    final_path = avatars_path / filename

    try:
        avatars_path.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(body)
        os.replace(tmp_path, final_path)
    except OSError as exc:
        logger.error("Failed to write avatar %s: %s", filename, exc)
        return False
    return True


def _store_normalised_avatar(
    body: bytes,
    avatars_dir: str | Path,
    user_id: int,
    variant: str,
) -> StoredAvatar | None:
    normalised = _normalise_image(body)
    if normalised is None:
        return None

    encoded, byte_size = normalised
    digest = hashlib.sha256(encoded).hexdigest()[:32]
    filename = f"{user_id}__{variant}__{digest}.webp"

    if not _write_atomic(avatars_dir, filename, encoded):
        return None

    logger.debug("Avatar saved: %s (%d bytes)", filename, byte_size)
    return StoredAvatar(
        filename=filename,
        content_type="image/webp",
        byte_size=byte_size,
    )


def save_uploaded_avatar(
    body: bytes,
    content_type: str,
    avatars_dir: str | Path,
    user_id: int,
) -> StoredAvatar | None:
    """Validate and persist an uploaded avatar image."""
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared not in _ALLOWED_CONTENT_TYPES:
        logger.warning("Uploaded avatar has unsupported content type: %s", declared)
        return None

    if len(body) > settings.avatar_max_upload_mb * 1024 * 1024:
        logger.warning("Uploaded avatar exceeds size limit: %d bytes", len(body))
        return None

    return _store_normalised_avatar(body, avatars_dir, user_id, "upload")


def is_safe_oidc_picture_url(url: str | None) -> bool:
    """Return True for an HTTPS OIDC picture URL that is safe to download."""
    if not url or len(url) > _MAX_PICTURE_URL_LENGTH:
        return False

    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if parsed.username or parsed.password or parsed.fragment:
        return False

    return is_safe_cover_import_url(url)


async def cache_oidc_avatar(
    picture_url: str,
    avatars_dir: str | Path,
    user_id: int,
    timeout: float | None = None,
    max_bytes: int | None = None,
) -> StoredAvatar | None:
    """Download an OIDC picture and store it as a normalised WebP avatar.

    Any failure returns ``None`` and is logged; callers must never fail an OIDC
    login because of an avatar problem.
    """
    if not is_safe_oidc_picture_url(picture_url):
        logger.warning("Refusing unsafe OIDC avatar URL: %s", picture_url)
        return None

    limit = max_bytes or settings.avatar_fetch_max_bytes
    request_timeout = timeout or settings.avatar_fetch_timeout_seconds

    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=request_timeout,
        ) as client:
            async with client.stream("GET", picture_url) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    logger.warning(
                        "OIDC avatar download returned %s for %s",
                        response.status_code,
                        picture_url,
                    )
                    return None

                declared_length = response.headers.get("content-length")
                if declared_length and declared_length.isdigit() and int(declared_length) > limit:
                    logger.warning(
                        "OIDC avatar exceeds size limit: %s bytes",
                        declared_length,
                    )
                    return None

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        logger.warning("OIDC avatar exceeded download limit")
                        return None
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("OIDC avatar download failed for %s: %s", picture_url, exc)
        return None

    return await run_in_threadpool(
        _store_normalised_avatar,
        bytes(body),
        avatars_dir,
        user_id,
        "oidc",
    )


def cleanup_orphan_avatars(session: Session, grace_minutes: int = 60) -> int:
    """Delete avatar files on disk that are no longer referenced by any row."""
    avatars_path = Path(settings.avatars_dir)
    if not avatars_path.exists():
        return 0

    referenced = {
        filename
        for filename in session.exec(select(UserImage.filename)).all()
        if filename
    }

    cutoff = time.time() - (grace_minutes * 60)
    deleted = 0
    for file_path in avatars_path.iterdir():
        if not file_path.is_file() or file_path.name in referenced:
            continue
        try:
            if file_path.stat().st_mtime > cutoff:
                logger.debug("Skipping recently modified avatar: %s", file_path.name)
                continue
            file_path.unlink()
            logger.info("Deleted orphaned avatar: %s", file_path.name)
            deleted += 1
        except OSError as exc:
            logger.warning("Failed to delete orphaned avatar %s: %s", file_path.name, exc)

    return deleted
