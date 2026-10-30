"""User profile endpoints — profile, settings, data reset, account deletion, API keys."""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlmodel import Session, col, select
from starlette.concurrency import run_in_threadpool

from app.auth import (
    clear_browser_session,
    ensure_password_complexity,
    generate_api_key,
    generate_embed_token,
    get_api_key_prefix,
    get_embed_token_prefix,
    get_password_hash,
    hash_api_key,
    hash_embed_token,
    require_user,
)
from app.config import settings as app_settings
from app.database import get_session
from app.models import ApiKey, AvatarSource, EmbedToken, User, UserImage, UserSettings
from app.oidc import oidc_provider_host
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyRead,
    AvatarOptionsRead,
    AvatarSourceUpdate,
    ConfirmationPhrase,
    DataResetDeleted,
    DataResetResponse,
    EmbedTokenCreate,
    EmbedTokenCreateResponse,
    EmbedTokenRead,
    EmbedTokenUpdate,
    ProfileUpdate,
    StatisticsRange,
    UserRead,
    UserSettingsRead,
    UserSettingsUpdate,
)
from app.services.avatar import (
    VARIANT_OIDC,
    VARIANT_UPLOAD,
    build_avatar_options,
    build_user_read,
    delete_avatar_image,
    get_user_image,
    image_has_file,
    upsert_avatar_image,
)
from app.services.avatar_storage import (
    cache_oidc_avatar,
    delete_avatar_file,
    save_uploaded_avatar,
)
from app.services.statistics import MAX_CUSTOM_RANGE_DAYS
from app.time_utils import utcnow
from app.services.user_deletion import (
    assert_not_last_admin,
    delete_user_account_data,
    delete_user_reading_data,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])
logger = logging.getLogger(__name__)


RESET_DATA_PHRASE: str = "DELETE ALL MY DATA"
DELETE_ACCOUNT_PHRASE: str = "DELETE MY ACCOUNT"
_AVATAR_WRITE_INTERVAL = timedelta(seconds=1)


def _ensure_avatar_write_interval(image: UserImage | None) -> None:
    """Reject avatar replacements that arrive faster than the write interval."""
    if image is not None and image.updated_at is not None:
        if utcnow() - image.updated_at < _AVATAR_WRITE_INTERVAL:
            raise HTTPException(
                status_code=429,
                detail="Avatar was updated too recently. Try again in a moment.",
            )


def _validate_confirmation(confirmation: str, expected_phrase: str) -> None:
    """Validate that *confirmation* matches *expected_phrase* exactly."""
    if confirmation.strip() != expected_phrase:
        raise HTTPException(status_code=400, detail="Confirmation phrase does not match.")


@router.get("", response_model=UserRead)
def get_profile(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserRead:
    """Return the current user's profile."""
    return build_user_read(session, current_user)


@router.patch("", response_model=UserRead)
def update_profile(
    user_in: ProfileUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserRead:
    """Update the current user's profile fields."""
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        ensure_password_complexity(update_data["password"])
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    current_user.sqlmodel_update(update_data)
    current_user.updated_at = utcnow()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return build_user_read(session, current_user)


@router.get("/avatar", response_model=AvatarOptionsRead)
def get_avatar_options(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> AvatarOptionsRead:
    """Return the current avatar state for the profile card."""
    return build_avatar_options(session, current_user, app_settings.avatars_dir)


@router.patch("/avatar", response_model=AvatarOptionsRead)
async def update_avatar_source(
    body: AvatarSourceUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> AvatarOptionsRead:
    """Change the selected avatar source."""
    assert current_user.id is not None

    if body.source == AvatarSource.upload:
        image = get_user_image(session, current_user.id, VARIANT_UPLOAD)
        if image is None or not image.filename:
            raise HTTPException(status_code=400, detail="No uploaded avatar available")
    elif body.source == AvatarSource.oidc:
        image = get_user_image(session, current_user.id, VARIANT_OIDC)
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="No OIDC picture available. Link OIDC or set a provider picture first.",
            )
        if not image.filename and image.external_url:
            stored = await cache_oidc_avatar(
                image.external_url,
                app_settings.avatars_dir,
                current_user.id,
                trusted_private_host=oidc_provider_host(),
            )
            if stored is None:
                raise HTTPException(
                    status_code=400,
                    detail="OIDC picture could not be downloaded",
                )
            upsert_avatar_image(
                session,
                current_user.id,
                VARIANT_OIDC,
                stored,
                external_url=image.external_url,
            )
        elif not image.filename:
            raise HTTPException(status_code=400, detail="OIDC picture is not cached")

    current_user.avatar_source = body.source
    current_user.updated_at = utcnow()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return build_avatar_options(session, current_user, app_settings.avatars_dir)


@router.post("/avatar/upload", response_model=AvatarOptionsRead)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> AvatarOptionsRead:
    """Upload a cropped avatar image."""
    assert current_user.id is not None
    previous = get_user_image(session, current_user.id, VARIANT_UPLOAD)
    _ensure_avatar_write_interval(previous)

    limit = app_settings.avatar_max_upload_mb * 1024 * 1024
    body = await file.read(limit + 1)
    if len(body) > limit:
        raise HTTPException(status_code=413, detail="Avatar image is too large")

    stored = await run_in_threadpool(
        save_uploaded_avatar,
        body,
        file.content_type or "",
        app_settings.avatars_dir,
        current_user.id,
    )
    if stored is None:
        raise HTTPException(
            status_code=422,
            detail="Avatar must be a valid PNG, JPEG, or WebP image",
        )

    previous_filename = previous.filename if previous else None
    upsert_avatar_image(
        session,
        current_user.id,
        VARIANT_UPLOAD,
        stored,
    )
    current_user.avatar_source = AvatarSource.upload
    current_user.updated_at = utcnow()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    if previous_filename and previous_filename != stored.filename:
        delete_avatar_file(previous_filename, app_settings.avatars_dir)
    return build_avatar_options(session, current_user, app_settings.avatars_dir)


@router.delete("/avatar/upload", response_model=AvatarOptionsRead)
def delete_uploaded_avatar(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> AvatarOptionsRead:
    """Remove the uploaded avatar and fall back to OIDC or animal."""
    assert current_user.id is not None
    filename = delete_avatar_image(
        session,
        current_user.id,
        VARIANT_UPLOAD,
    )

    if current_user.avatar_source == AvatarSource.upload:
        oidc = get_user_image(session, current_user.id, VARIANT_OIDC)
        current_user.avatar_source = (
            AvatarSource.oidc
            if image_has_file(oidc, app_settings.avatars_dir)
            else AvatarSource.animal
        )

    current_user.updated_at = utcnow()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    if filename:
        delete_avatar_file(filename, app_settings.avatars_dir)
    return build_avatar_options(session, current_user, app_settings.avatars_dir)


@router.post("/avatar/refresh-oidc", response_model=AvatarOptionsRead)
async def refresh_oidc_avatar(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> AvatarOptionsRead:
    """Re-download the cached OIDC picture from its provider URL."""
    assert current_user.id is not None
    image = get_user_image(session, current_user.id, VARIANT_OIDC)
    if image is None or not image.external_url:
        raise HTTPException(status_code=400, detail="No OIDC picture URL is stored")
    _ensure_avatar_write_interval(image)

    stored = await cache_oidc_avatar(
        image.external_url,
        app_settings.avatars_dir,
        current_user.id,
        trusted_private_host=oidc_provider_host(),
    )
    if stored is None:
        raise HTTPException(status_code=400, detail="OIDC picture could not be downloaded")

    previous = image.filename
    upsert_avatar_image(
        session,
        current_user.id,
        VARIANT_OIDC,
        stored,
        external_url=image.external_url,
    )
    current_user.updated_at = utcnow()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    if previous and previous != stored.filename:
        delete_avatar_file(previous, app_settings.avatars_dir)
    return build_avatar_options(session, current_user, app_settings.avatars_dir)


@router.get("/settings", response_model=UserSettingsRead)
def get_settings(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserSettingsRead:
    """Return the current user's settings."""
    assert current_user.id is not None
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    ).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, language="en")
        session.add(settings)
        session.commit()
        session.refresh(settings)
    assert settings.user_id is not None
    return UserSettingsRead(
        user_id=settings.user_id,
        language=settings.language,
        timezone=settings.timezone,
        theme=settings.theme,
        custom_theme=settings.custom_theme,
        goal_pages_per_day_enabled=settings.goal_pages_per_day_enabled,
        goal_pages_per_day=settings.goal_pages_per_day,
        goal_pages_per_month_enabled=settings.goal_pages_per_month_enabled,
        goal_pages_per_month=settings.goal_pages_per_month,
        goal_books_per_month_enabled=settings.goal_books_per_month_enabled,
        goal_books_per_month=settings.goal_books_per_month,
        goal_books_per_year_enabled=settings.goal_books_per_year_enabled,
        goal_books_per_year=settings.goal_books_per_year,
        gamification_enabled=settings.gamification_enabled,
        auto_set_date_started=settings.auto_set_date_started,
        auto_set_date_finished=settings.auto_set_date_finished,
        statistics_range=StatisticsRange(settings.statistics_range),
        statistics_custom_from=settings.statistics_custom_from,
        statistics_custom_to=settings.statistics_custom_to,
    )


@router.patch("/settings", response_model=UserSettingsRead)
def update_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserSettingsRead:
    """Update the current user's settings."""
    assert current_user.id is not None
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    ).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, language="en")
    update_data = body.model_dump(exclude_unset=True)
    if "statistics_range" in update_data and update_data["statistics_range"] is None:
        raise HTTPException(status_code=422, detail="statistics_range cannot be null")
    custom_from = update_data.get("statistics_custom_from", settings.statistics_custom_from)
    custom_to = update_data.get("statistics_custom_to", settings.statistics_custom_to)
    statistics_range = update_data.get("statistics_range", settings.statistics_range)
    if statistics_range == "custom" and (custom_from is None or custom_to is None):
        raise HTTPException(status_code=422, detail="Custom range requires both dates")
    if custom_from is not None and custom_to is not None and custom_from > custom_to:
        raise HTTPException(status_code=422, detail="statistics_custom_from cannot be after statistics_custom_to")
    if custom_from is not None and custom_to is not None and (custom_to - custom_from).days > MAX_CUSTOM_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Statistics custom range cannot exceed 25 years")
    settings.sqlmodel_update(update_data)
    if settings.theme != 'custom':
        settings.custom_theme = None
    session.add(settings)
    session.commit()
    session.refresh(settings)
    assert settings.user_id is not None
    return UserSettingsRead(
        user_id=settings.user_id,
        language=settings.language,
        timezone=settings.timezone,
        theme=settings.theme,
        custom_theme=settings.custom_theme,
        goal_pages_per_day_enabled=settings.goal_pages_per_day_enabled,
        goal_pages_per_day=settings.goal_pages_per_day,
        goal_pages_per_month_enabled=settings.goal_pages_per_month_enabled,
        goal_pages_per_month=settings.goal_pages_per_month,
        goal_books_per_month_enabled=settings.goal_books_per_month_enabled,
        goal_books_per_month=settings.goal_books_per_month,
        goal_books_per_year_enabled=settings.goal_books_per_year_enabled,
        goal_books_per_year=settings.goal_books_per_year,
        gamification_enabled=settings.gamification_enabled,
        auto_set_date_started=settings.auto_set_date_started,
        auto_set_date_finished=settings.auto_set_date_finished,
        statistics_range=StatisticsRange(settings.statistics_range),
        statistics_custom_from=settings.statistics_custom_from,
        statistics_custom_to=settings.statistics_custom_to,
    )


@router.post("/reset-data", response_model=DataResetResponse)
def reset_data(
    body: ConfirmationPhrase,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> DataResetResponse:
    """Delete all reading-related data owned by the current user.

    Preserves account, settings, API keys, and OIDC link.
    Requires exact confirmation phrase.
    """
    _validate_confirmation(body.confirmation, RESET_DATA_PHRASE)
    assert current_user.id is not None

    try:
        deleted = delete_user_reading_data(session, current_user.id, app_settings.covers_dir)
        session.commit()
    except Exception:
        session.rollback()
        raise

    logger.warning(
        "User %s reset personal data: books=%s tags=%s authors=%s progress_entries=%s",
        current_user.id, deleted.books, deleted.tags, deleted.authors, deleted.progress_entries,
    )

    return DataResetResponse(
        message="profile.dataResetSuccess",
        deleted=DataResetDeleted(
            books=deleted.books,
            tags=deleted.tags,
            authors=deleted.authors,
            progress_entries=deleted.progress_entries,
        ),
    )


@router.delete("/account", status_code=204)
def delete_own_account(
    body: ConfirmationPhrase,
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete the current user account and all related data.

    Operation is blocked when the user is the last admin in the system.
    Requires exact confirmation phrase.
    """
    _validate_confirmation(body.confirmation, DELETE_ACCOUNT_PHRASE)
    assert_not_last_admin(session, current_user)
    assert current_user.id is not None

    try:
        deleted = delete_user_account_data(session, current_user, app_settings.covers_dir)
        session.commit()
    except Exception:
        session.rollback()
        raise

    for filename in deleted.avatar_filenames:
        delete_avatar_file(filename, app_settings.avatars_dir)

    clear_browser_session(request)
    logger.warning("User %s deleted own account", current_user.id)


@router.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[ApiKeyRead]:
    """List non-revoked API keys for the current user."""
    keys = session.exec(
        select(ApiKey).where(
            ApiKey.user_id == current_user.id,
            col(ApiKey.revoked_at).is_(None),
        ).order_by(col(ApiKey.created_at).desc())
    ).all()
    return [ApiKeyRead.model_validate(k) for k in keys]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ApiKeyCreateResponse:
    """Create a new API key for the current user."""
    assert current_user.id is not None
    plain_key = generate_api_key()
    key = ApiKey(
        user_id=current_user.id,
        key_prefix=get_api_key_prefix(plain_key),
        key_hash=hash_api_key(plain_key),
        description=body.description,
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return ApiKeyCreateResponse(key=plain_key, api_key=ApiKeyRead.model_validate(key))


@router.delete("/api-keys/{api_key_id}", status_code=204)
def delete_api_key(
    api_key_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    """Revoke an API key by ID."""
    key = session.get(ApiKey, api_key_id)
    if not key or key.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="API key not found")

    key.revoked_at = utcnow()
    session.add(key)
    session.commit()


@router.get("/embed-tokens", response_model=list[EmbedTokenRead])
def list_embed_tokens(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[EmbedTokenRead]:
    """List non-revoked embed tokens for the current user."""
    tokens = session.exec(
        select(EmbedToken).where(
            EmbedToken.user_id == current_user.id,
            col(EmbedToken.revoked_at).is_(None),
        ).order_by(col(EmbedToken.created_at).desc())
    ).all()
    return [EmbedTokenRead.model_validate(t) for t in tokens]


@router.post("/embed-tokens", response_model=EmbedTokenCreateResponse, status_code=201)
def create_embed_token(
    body: EmbedTokenCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> EmbedTokenCreateResponse:
    """Create a new embed token for the current user."""
    assert current_user.id is not None
    plain_token = generate_embed_token()
    token = EmbedToken(
        user_id=current_user.id,
        name=body.name,
        token_prefix=get_embed_token_prefix(plain_token),
        token_hash=hash_embed_token(plain_token),
        allowed_origins=body.allowed_origins or None,
        expires_at=body.expires_at,
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    return EmbedTokenCreateResponse(
        token=plain_token,
        embed_token=EmbedTokenRead.model_validate(token),
    )


@router.patch("/embed-tokens/{token_id}", response_model=EmbedTokenRead)
def update_embed_token(
    token_id: int,
    body: EmbedTokenUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> EmbedTokenRead:
    """Update name, allowed_origins, or expires_at for an embed token."""
    token = session.get(EmbedToken, token_id)
    if not token or token.user_id != current_user.id or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Embed token not found")

    update_data = body.model_dump(exclude_unset=True)
    token.sqlmodel_update(update_data)
    session.add(token)
    session.commit()
    session.refresh(token)
    return EmbedTokenRead.model_validate(token)


@router.post("/embed-tokens/{token_id}/rotate", response_model=EmbedTokenCreateResponse)
def rotate_embed_token(
    token_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> EmbedTokenCreateResponse:
    """Revoke the current embed token and create a new one with the same settings."""
    token = session.get(EmbedToken, token_id)
    if not token or token.user_id != current_user.id or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Embed token not found")

    now = utcnow()
    if token.expires_at is not None and token.expires_at < now:
        raise HTTPException(
            status_code=409,
            detail="Expired embed tokens cannot be rotated",
        )

    token.revoked_at = now
    session.add(token)
    assert current_user.id is not None
    plain_token = generate_embed_token()
    new_token = EmbedToken(
        user_id=current_user.id,
        name=token.name,
        token_prefix=get_embed_token_prefix(plain_token),
        token_hash=hash_embed_token(plain_token),
        scopes=token.scopes,
        allowed_origins=token.allowed_origins,
        expires_at=token.expires_at,
    )
    session.add(new_token)
    session.commit()
    session.refresh(new_token)
    return EmbedTokenCreateResponse(
        token=plain_token,
        embed_token=EmbedTokenRead.model_validate(new_token),
    )


@router.delete("/embed-tokens/{token_id}", status_code=204)
def delete_embed_token(
    token_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    """Revoke an embed token by ID."""
    token = session.get(EmbedToken, token_id)
    if not token or token.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Embed token not found")

    token.revoked_at = utcnow()
    session.add(token)
    session.commit()
