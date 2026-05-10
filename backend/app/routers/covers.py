"""
Router for serving locally cached cover images.
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.services.cover_storage import resolve_cover_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/covers", tags=["covers"])


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
