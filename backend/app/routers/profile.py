"""User profile endpoints — profile, settings, data reset, account deletion, API keys."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth import (
    clear_browser_session,
    ensure_password_complexity,
    generate_api_key,
    get_api_key_prefix,
    get_password_hash,
    hash_api_key,
    require_user,
)
from app.config import settings as app_settings
from app.database import get_session
from app.models import ApiKey, User, UserSettings
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyRead,
    ConfirmationPhrase,
    DataResetDeleted,
    DataResetResponse,
    ProfileUpdate,
    UserRead,
    UserSettingsRead,
    UserSettingsUpdate,
)
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


def _validate_confirmation(confirmation: str, expected_phrase: str) -> None:
    """Validate that *confirmation* matches *expected_phrase* exactly."""
    if confirmation.strip() != expected_phrase:
        raise HTTPException(status_code=400, detail="Confirmation phrase does not match.")


@router.get("", response_model=UserRead)
def get_profile(current_user: User = Depends(require_user)) -> User:
    """Return the current user's profile."""
    return current_user


@router.patch("", response_model=UserRead)
def update_profile(
    user_in: ProfileUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> User:
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
    return current_user


@router.get("/settings", response_model=UserSettingsRead)
def get_settings(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserSettingsRead:
    """Return the current user's settings."""
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    ).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, language="en")
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return UserSettingsRead(
        user_id=settings.user_id,
        language=settings.language,
        timezone=settings.timezone,
        quote_service_enabled=app_settings.dashboard_quote_enabled,
        theme=settings.theme,
        custom_theme=settings.custom_theme,
    )


@router.patch("/settings", response_model=UserSettingsRead)
def update_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> UserSettingsRead:
    """Update the current user's settings."""
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    ).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, language="en")
    update_data = body.model_dump(exclude_unset=True)
    settings.sqlmodel_update(update_data)
    if settings.theme != 'custom':
        settings.custom_theme = None
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return UserSettingsRead(
        user_id=settings.user_id,
        language=settings.language,
        timezone=settings.timezone,
        quote_service_enabled=app_settings.dashboard_quote_enabled,
        theme=settings.theme,
        custom_theme=settings.custom_theme,
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

    try:
        deleted = delete_user_reading_data(session, current_user.id, app_settings.covers_dir)
        session.commit()
    except Exception:
        session.rollback()
        raise

    logger.warning(
        "User %s reset personal data: books=%s tags=%s progress_entries=%s",
        current_user.id, deleted.books, deleted.tags, deleted.progress_entries,
    )

    return DataResetResponse(
        message="profile.dataResetSuccess",
        deleted=DataResetDeleted(
            books=deleted.books,
            tags=deleted.tags,
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

    try:
        delete_user_account_data(session, current_user, app_settings.covers_dir)
        session.commit()
    except Exception:
        session.rollback()
        raise

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
            ApiKey.revoked_at.is_(None),
        )
    ).all()
    return [ApiKeyRead.model_validate(k) for k in keys]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ApiKeyCreateResponse:
    """Create a new API key for the current user."""
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
