from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import (
    ensure_password_complexity,
    generate_api_key,
    get_api_key_prefix,
    get_password_hash,
    hash_api_key,
    require_user_by_api_key,
)
from app.database import get_session
from app.models import ApiKey, User, UserSettings
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyRead,
    ProfileUpdate,
    UserRead,
    UserSettingsRead,
    UserSettingsUpdate,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=UserRead)
def get_profile(current_user: User = Depends(require_user_by_api_key)) -> User:
    return current_user


@router.patch("", response_model=UserRead)
def update_profile(
    user_in: ProfileUpdate,
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> User:
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        ensure_password_complexity(update_data["password"])
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    current_user.sqlmodel_update(update_data)
    current_user.updated_at = datetime.now(timezone.utc)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.get("/settings", response_model=UserSettingsRead)
def get_settings(
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> UserSettings:
    settings = session.exec(select(UserSettings).where(UserSettings.user_id == current_user.id)).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, language="en")
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@router.patch("/settings", response_model=UserSettingsRead)
def update_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> UserSettings:
    settings = session.exec(select(UserSettings).where(UserSettings.user_id == current_user.id)).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, language="en")
    settings.sqlmodel_update(body.model_dump(exclude_unset=True))
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


@router.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> list[ApiKeyRead]:
    keys = session.exec(
        select(ApiKey).where(ApiKey.user_id == current_user.id, ApiKey.revoked_at.is_(None))
    ).all()
    return [ApiKeyRead.model_validate(k) for k in keys]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> ApiKeyCreateResponse:
    plain_key = generate_api_key()
    key = ApiKey(
        user_id=current_user.id,
        key_prefix=get_api_key_prefix(plain_key),
        key_hash=hash_api_key(plain_key),
        description=body.description,
        is_primary=False,
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return ApiKeyCreateResponse(key=plain_key, api_key=ApiKeyRead.model_validate(key))


@router.delete("/api-keys/{api_key_id}", status_code=204)
def delete_api_key(
    api_key_id: int,
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> None:
    key = session.get(ApiKey, api_key_id)
    if not key or key.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.is_primary:
        raise HTTPException(status_code=403, detail="Cannot delete primary API key")

    key.revoked_at = datetime.now(timezone.utc)
    session.add(key)
    session.commit()
