"""Data export and import endpoints — export ZIP, import parse/validate/execute with SSE streaming."""

import json
import asyncio
from datetime import datetime
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
    DataImportPreviewRequest,
    DataImportPreviewResponse,
    DataImportRunRequest,
    DataImportSuggestRequest,
    DataImportSuggestResponse,
    DataImportValidateRequest,
    DataImportValidateResponse,
    ImportFieldConfig,
)
from app.time_utils import utcnow
from app.services.data_export import build_export_zip
from app.services.data_import import (
    BOOK_IMPORT_FIELDS,
    PREDEFINED_MAPPINGS,
    compute_schema_fingerprint,
    execute_import,
    get_predefined_mapping,
    load_parsed_upload,
    parse_upload,
    preview_import,
    suggest_mapping,
    validate_import,
)

router = APIRouter(prefix="/api/data", tags=["data"])


def _mapping_read(model: ImportMapping) -> DataImportMappingRead:
    """Convert an ImportMapping DB model to its response schema."""
    raw_mapping = json.loads(model.mapping_json)
    return DataImportMappingRead(
        id=model.id or 0,
        name=model.name,
        source_fields=json.loads(model.source_fields_json),
        mapping={k: ImportFieldConfig(**v) for k, v in raw_mapping.items()},
        created_at=model.created_at,
        updated_at=model.updated_at,
        is_predefined=False,
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

    mapping_dict = {k: v.model_dump() for k, v in body.mapping.items()}
    if existing:
        existing.source_fields_json = json.dumps(body.source_fields)
        existing.mapping_json = json.dumps(mapping_dict)
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
        mapping_json=json.dumps(mapping_dict),
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
    """List saved and predefined import mappings."""
    epoch = datetime(2000, 1, 1)
    predefined: list[DataImportMappingListItem] = [
        DataImportMappingListItem(
            id=int(pm["id"]),  # type: ignore[arg-type]
            name=str(pm["name"]),
            created_at=epoch,
            updated_at=epoch,
            is_predefined=True,
        )
        for pm in PREDEFINED_MAPPINGS
    ]
    rows = list(
        session.exec(
            select(ImportMapping)
            .where(ImportMapping.user_id == current_user.id)
            .order_by(ImportMapping.updated_at.desc())
        ).all()
    )
    user_mappings = [
        DataImportMappingListItem(
            id=row.id or 0,
            name=row.name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    return predefined + user_mappings


@router.get("/import/mappings/{mapping_id}", response_model=DataImportMappingRead)
def get_import_mapping(
    mapping_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> DataImportMappingRead:
    """Return a single import mapping by ID (supports predefined mappings with negative IDs)."""
    if mapping_id < 0:
        pm = get_predefined_mapping(mapping_id)
        if pm is None:
            raise HTTPException(status_code=404, detail="Predefined mapping not found.")
        raw_mapping: Any = pm.get("mapping")
        raw_sources: Any = pm.get("source_fields", [])
        return DataImportMappingRead(
            id=mapping_id,
            name=str(pm.get("name", "")),
            source_fields=list(raw_sources),
            mapping={k: ImportFieldConfig(**v) for k, v in raw_mapping.items()},
            created_at=datetime(2000, 1, 1),
            updated_at=datetime(2000, 1, 1),
            is_predefined=True,
        )
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
    """Delete a saved import mapping. Predefined mappings cannot be deleted."""
    if mapping_id < 0:
        raise HTTPException(status_code=403, detail="Predefined mappings cannot be deleted.")
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


@router.post("/import/preview", response_model=DataImportPreviewResponse)
def preview_import_data(
    body: DataImportPreviewRequest,
    current_user: User = Depends(require_user),
) -> DataImportPreviewResponse:
    """Preview how a mapping and transforms will affect the first rows."""
    try:
        payload = preview_import(body.file_id, current_user, body.mapping)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DataImportPreviewResponse.model_validate(payload)


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
            import_failed_rows = 0
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
                        import_failed_rows = event.get("failed", 0)
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
                pass  # import file is cleaned up by the periodic temp file job

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
