"""Admin user management endpoints — list, create, update, delete users."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import (
    ensure_password_complexity,
    get_password_hash,
    require_admin,
)
from app.database import get_session
from app.models import ApiKey, User, UserRole, UserSettings
from app.schemas import UserAdminUpdate, UserCreate, UserRead
from app.services.user_deletion import assert_not_last_admin
from app.time_utils import utcnow

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[User]:
    """List all users (admin only)."""
    users = session.exec(select(User).order_by(User.created_at)).all()
    return list(users)


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

    session.add(UserSettings(user_id=user.id, language="en"))
    session.commit()
    return {"user": UserRead.model_validate(user)}


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
    return user


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

    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user_id)).first()
    if settings:
        session.delete(settings)

    session.delete(user)
    session.commit()
