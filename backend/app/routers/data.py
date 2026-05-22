"""Data export and import endpoints — export ZIP, import parse/validate/execute with SSE streaming."""

import json
import asyncio
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth import require_user
from app.config import settings
from app.database import engine, get_session
from app.models import ImportMapping, User
from app.schemas import (
    DataExportRequest,
    DataImportMappingListItem,
    DataImportMappingRead,
    DataImportMappingSave,
    DataImportParseResponse,
    DataImportRunRequest,
    DataImportSuggestRequest,
    DataImportSuggestResponse,
    DataImportValidateRequest,
    DataImportValidateResponse,
)
from app.time_utils import utcnow
from app.services.data_export import build_export_zip
from app.services.data_import import (
    BOOK_IMPORT_FIELDS,
    compute_schema_fingerprint,
    delete_parsed_upload,
    execute_import,
    load_parsed_upload,
    parse_upload,
    suggest_mapping,
    validate_import,
)

router = APIRouter(prefix="/api/data", tags=["data"])


def _mapping_read(model: ImportMapping) -> DataImportMappingRead:
    """Convert an ImportMapping DB model to its response schema."""
    return DataImportMappingRead(
        id=model.id or 0,
        name=model.name,
        source_fields=json.loads(model.source_fields_json),
        mapping=json.loads(model.mapping_json),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.post("/export")
def export_data(
    body: DataExportRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    """Export user data as a ZIP archive with CSV or JSON datasets."""
    if not body.datasets:
        raise HTTPException(status_code=400, detail="Select at least one dataset to export.")
    zip_bytes, filename = build_export_zip(
        session=session,
        user=current_user,
        datasets=body.datasets,
        export_format=body.format,
        covers_dir=settings.covers_dir,
    )
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/parse", response_model=DataImportParseResponse)
async def parse_import_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
) -> DataImportParseResponse:
    """Parse an uploaded CSV or JSON import file and return field info and samples."""
    allowed_content_types = {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/json",
        "text/plain",
    }
    if file.content_type and file.content_type not in allowed_content_types:
        raise HTTPException(status_code=415, detail="Unsupported upload content type. Use CSV or JSON files.")
    try:
        payload = parse_upload(await file.read(), file.filename or "upload", current_user.id)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DataImportParseResponse.model_validate(payload)


@router.post("/import/suggest-mapping", response_model=DataImportSuggestResponse)
def suggest_import_mapping(
    body: DataImportSuggestRequest,
    current_user: User = Depends(require_user),
) -> DataImportSuggestResponse:
    """Suggest a field-name mapping based on the parsed import file."""
    try:
        parsed = load_parsed_upload(body.file_id, current_user.id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DataImportSuggestResponse(
        suggested_mapping=suggest_mapping(parsed.get("source_fields", [])),
        db_fields=BOOK_IMPORT_FIELDS,
    )


@router.post("/import/mappings", response_model=DataImportMappingRead, status_code=201)
def save_import_mapping(
    body: DataImportMappingSave,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> DataImportMappingRead:
    """Create or update a saved column-mapping configuration."""
    now = utcnow()
    schema_fingerprint = compute_schema_fingerprint(body.source_fields)

    existing = session.exec(
        select(ImportMapping).where(
            ImportMapping.user_id == current_user.id,
            ImportMapping.name == body.name,
        )
    ).first()

    if existing:
        existing.source_fields_json = json.dumps(body.source_fields)
        existing.mapping_json = json.dumps(body.mapping)
        existing.schema_fingerprint = schema_fingerprint
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return _mapping_read(existing)

    mapping = ImportMapping(
        user_id=current_user.id,
        name=body.name,
        schema_fingerprint=schema_fingerprint,
        source_fields_json=json.dumps(body.source_fields),
        mapping_json=json.dumps(body.mapping),
        created_at=now,
        updated_at=now,
    )
    session.add(mapping)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A mapping with this name already exists.") from exc
    session.refresh(mapping)
    return _mapping_read(mapping)


@router.get("/import/mappings", response_model=list[DataImportMappingListItem])
def list_import_mappings(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[DataImportMappingListItem]:
    """List saved import mappings, newest first."""
    rows = list(
        session.exec(
            select(ImportMapping)
            .where(ImportMapping.user_id == current_user.id)
            .order_by(ImportMapping.updated_at.desc())
        ).all()
    )
    return [
        DataImportMappingListItem(
            id=row.id or 0,
            name=row.name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get("/import/mappings/{mapping_id}", response_model=DataImportMappingRead)
def get_import_mapping(
    mapping_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> DataImportMappingRead:
    """Return a single saved import mapping by ID."""
    row = session.get(ImportMapping, mapping_id)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Import mapping not found.")
    return _mapping_read(row)


@router.delete("/import/mappings/{mapping_id}", status_code=204)
def delete_import_mapping(
    mapping_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete a saved import mapping."""
    row = session.get(ImportMapping, mapping_id)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Import mapping not found.")
    session.delete(row)
    session.commit()


@router.post("/import/validate", response_model=DataImportValidateResponse)
def validate_import_data(
    body: DataImportValidateRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> DataImportValidateResponse:
    """Validate an import file against the DB schema and existing data."""
    try:
        payload = validate_import(
            body.file_id, current_user, body.mapping, session,
            create_progress_for_read=body.create_progress_for_read,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DataImportValidateResponse.model_validate(payload)


@router.post("/import/execute")
async def execute_import_data(
    body: DataImportRunRequest,
    current_user: User = Depends(require_user),
    session_template: Session = Depends(get_session),
) -> StreamingResponse:
    """Execute an import, streaming progress and results as Server-Sent Events."""
    stream_bind = session_template.get_bind() or engine

    async def event_generator():
        with Session(stream_bind) as session:
            completed = False
            final_error: str | None = None
            try:
                async for event in execute_import(
                    file_id=body.file_id,
                    user=current_user,
                    mapping=body.mapping,
                    session=session,
                    import_mode=body.import_mode,
                    create_progress_for_read=body.create_progress_for_read,
                ):
                    if event.get("event") == "complete":
                        completed = True
                    if event.get("event") == "error":
                        final_error = str(event.get("message") or "Import failed")
                    yield f"data: {json.dumps(event)}\n\n"
                if not completed and final_error is None:
                    session.rollback()
            except asyncio.CancelledError:
                session.rollback()
                raise
            except FileNotFoundError as exc:
                final_error = str(exc)
                yield f"data: {json.dumps({'event': 'error', 'message': str(exc)})}\n\n"
            except Exception:
                session.rollback()
                final_error = 'error.importExecutionFailed'
                yield f"data: {json.dumps({'event': 'error', 'message': 'error.importExecutionFailed'})}\n\n"
            finally:
                if completed or final_error is not None:
                    delete_parsed_upload(body.file_id, current_user.id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
