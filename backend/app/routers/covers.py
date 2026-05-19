"""
Router for serving and uploading locally cached cover images.
"""

import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.auth import require_user
from app.models import User
from app.schemas import CoverCandidateImportRequest
from app.services.cover_storage import resolve_cover_path, save_uploaded_cover
from app.services.cover_import import import_cover_from_url, is_safe_cover_import_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/covers", tags=["covers"])


@router.post("/upload")
async def upload_cover(file: UploadFile = File(...), user: User = Depends(require_user)) -> dict:
    """Accept a multipart image upload and return its local cover URL.

    Returns ``{"cover_url": "/api/covers/<filename>"}`` on success, or
    HTTP 422 if the file is not a valid or large-enough image.
    """
    body = await file.read()
    content_type = file.content_type or ""

    filename = save_uploaded_cover(body, content_type, settings.covers_dir, user.id)
    if filename is None:
        raise HTTPException(
            status_code=422,
            detail="Invalid image or file is too small (minimum 5 KB).",
        )

    logger.info("Cover uploaded: %s", filename)
    return {"cover_url": f"/api/covers/{filename}"}


@router.get("/{filename}")
async def get_cover(filename: str) -> FileResponse:
    """Serve a locally cached cover image by filename."""
    # Path-traversal guard: reject any filename that tries to escape the directory.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = resolve_cover_path(settings.covers_dir, filename)
    if file_path is None:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not file_path.exists():
        logger.debug("Cover not found: %s", filename)
        raise HTTPException(status_code=404, detail="Cover not found.")

    return FileResponse(file_path)


@router.post("/import-url")
async def import_cover_url(payload: CoverCandidateImportRequest, user: User = Depends(require_user)) -> dict:
    url = payload.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=422, detail="Invalid cover URL")
    if not is_safe_cover_import_url(url):
        raise HTTPException(status_code=422, detail="URL points to restricted network range")

    filename = await import_cover_from_url(
        url,
        settings.covers_dir,
        user.id,
        settings.cover_import_timeout_seconds,
    )

    if filename is None:
        raise HTTPException(status_code=422, detail="Unable to import cover from URL")

    return {"cover_url": f"/api/covers/{filename}"}
