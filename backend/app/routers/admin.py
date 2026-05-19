import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.auth import require_admin
from app.config import settings
from app.database import get_session
from app.models import User
from app.services.backup_restore import (
    create_backup,
    restore_backup,
    validate_backup_zip,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

MAX_RESTORE_SIZE = settings.max_restore_size_mb * 1024 * 1024


@router.get("/backup")
def backup_download(
    _admin: User = Depends(require_admin),
    _session: Session = Depends(get_session),
):
    try:
        data = create_backup(
            database_url=settings.database_url,
            data_dir=settings.data_dir,
            covers_dir=settings.covers_dir,
            import_temp_dir=settings.import_temp_dir,
        )
    except RuntimeError as exc:
        if "already in progress" in str(exc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        logger.exception("Backup failed")
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}")
    except Exception as exc:
        logger.exception("Backup failed")
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}")

    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="librislog-backup-{timestamp}.zip"',
            "Content-Length": str(len(data)),
        },
    )


@router.post("/validate-backup")
def validate_backup(
    file: UploadFile,
    _admin: User = Depends(require_admin),
):
    contents = file.file.read(MAX_RESTORE_SIZE + 1)
    if len(contents) > MAX_RESTORE_SIZE:
        raise HTTPException(status_code=400, detail="Backup file exceeds maximum size")

    try:
        result = validate_backup_zip(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not result["valid"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Invalid backup file"))

    return result


@router.post("/restore")
def restore(
    file: UploadFile,
    _admin: User = Depends(require_admin),
):
    contents = file.file.read(MAX_RESTORE_SIZE + 1)
    if len(contents) > MAX_RESTORE_SIZE:
        raise HTTPException(status_code=400, detail="Backup file exceeds maximum size")

    try:
        validation = validate_backup_zip(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation.get("error", "Invalid backup file"))

    try:
        result = restore_backup(
            backup_zip_bytes=contents,
            database_url=settings.database_url,
            data_dir=settings.data_dir,
            covers_dir=settings.covers_dir,
            import_temp_dir=settings.import_temp_dir,
        )
    except RuntimeError as exc:
        if "already in progress" in str(exc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        logger.exception("Restore failed")
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Restore failed")
        raise HTTPException(status_code=500, detail=f"Restore failed: {exc}")

    return result
