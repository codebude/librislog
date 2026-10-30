"""Admin user management endpoints — list, create, update, delete users."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session, col, select

from app.auth import (
    ensure_password_complexity,
    get_password_hash,
    require_admin,
    require_user,
)
from app.config import settings
from app.database import get_session
from app.models import ApiKey, User, UserRole, UserSettings
from app.schemas import UserAdminUpdate, UserCreate, UserRead
from app.services.avatar import (
    build_user_read,
    delete_all_user_avatar_images,
    load_avatar_urls,
    selected_avatar_image,
)
from app.services.avatar_storage import delete_avatar_file, resolve_avatar_path
from app.services.user_deletion import assert_not_last_admin
from app.time_utils import utcnow

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[UserRead]:
    """List all users (admin only)."""
    users = session.exec(select(User).order_by(col(User.created_at))).all()
    avatar_urls = load_avatar_urls(session, users)
    result: list[UserRead] = []
    for user in users:
        assert user.id is not None
        result.append(
            UserRead(
                id=user.id,
                firstname=user.firstname,
                lastname=user.lastname,
                email=user.email,
                role=user.role,
                created_at=user.created_at,
                avatar_url=avatar_urls.get(user.id),
            )
        )
    return result


@router.post("", status_code=201)
def create_user(
    user_in: UserCreate,
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    """Create a new user (admin only)."""
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    ensure_password_complexity(user_in.password)

    user = User(
        firstname=user_in.firstname,
        lastname=user_in.lastname,
        email=user_in.email,
        role=user_in.role,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    session.add(UserSettings(user_id=user.id, language="en"))
    session.commit()
    session.refresh(user)
    return {"user": build_user_read(session, user)}


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_in: UserAdminUpdate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> User:
    """Update a user's profile fields (admin only)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_in.model_dump(exclude_unset=True)
    if admin.id == user_id and "role" in update_data and update_data["role"] != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change your own admin role",
        )

    if "email" in update_data and update_data["email"] != user.email:
        existing = session.exec(select(User).where(User.email == update_data["email"])).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
    if "password" in update_data:
        ensure_password_complexity(update_data["password"])
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    user.sqlmodel_update(update_data)
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return build_user_read(session, user)


@router.get("/{user_id}/avatar")
def get_user_avatar(
    user_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> FileResponse:
    """Serve a user's effective avatar image."""
    if current_user.id != user_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=404, detail="Avatar not found")

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    image = selected_avatar_image(session, user)
    if image is None or not image.filename:
        raise HTTPException(status_code=404, detail="Avatar not found")

    path = resolve_avatar_path(image.filename, settings.avatars_dir)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")

    return FileResponse(
        path,
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    """Delete a user account (admin only, cannot delete self)."""
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete your own account here. Use Profile > Danger Zone.",
        )

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    assert_not_last_admin(session, user)

    keys = session.exec(select(ApiKey).where(ApiKey.user_id == user_id)).all()
    for key in keys:
        key.revoked_at = utcnow()
        session.add(key)

    user_settings = session.exec(select(UserSettings).where(UserSettings.user_id == user_id)).first()
    if user_settings:
        session.delete(user_settings)

    avatar_filenames = delete_all_user_avatar_images(session, user_id)

    session.delete(user)
    session.commit()
    for filename in avatar_filenames:
        delete_avatar_file(filename, settings.avatars_dir)
