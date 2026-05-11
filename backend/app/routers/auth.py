from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import (
    ensure_password_complexity,
    decrypt_api_key,
    encrypt_api_key,
    generate_api_key,
    get_api_key_prefix,
    get_password_hash,
    hash_api_key,
    require_user_by_api_key,
    verify_password,
)
from app.database import get_session
from app.models import ApiKey, User, UserRole, UserSettings
from app.schemas import SetupRequest, UserLogin, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/setup-required")
def setup_required(session: Session = Depends(get_session)) -> dict:
    admin = session.exec(select(User).where(User.role == UserRole.admin).limit(1)).first()
    return {"required": admin is None}


@router.post("/setup")
def setup(request: SetupRequest, session: Session = Depends(get_session)) -> dict:
    admin_exists = session.exec(select(User).where(User.role == UserRole.admin).limit(1)).first()
    if admin_exists:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup already completed")

    existing_email = session.exec(select(User).where(User.email == request.email)).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    ensure_password_complexity(request.password)

    user = User(
        firstname=request.firstname,
        lastname=request.lastname,
        email=request.email,
        role=UserRole.admin,
        hashed_password=get_password_hash(request.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    session.add(UserSettings(user_id=user.id, language="en"))

    main_key = generate_api_key()
    session.add(
        ApiKey(
            user_id=user.id,
            key_prefix=get_api_key_prefix(main_key),
            key_hash=hash_api_key(main_key),
            key_encrypted=encrypt_api_key(main_key),
            is_primary=True,
            description="Primary app key",
        )
    )
    session.commit()
    return {"user": UserRead.model_validate(user), "api_key": main_key}


@router.post("/login")
def login(credentials: UserLogin, session: Session = Depends(get_session)) -> dict:
    user = session.exec(select(User).where(User.email == credentials.email)).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    primary_key = session.exec(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.is_primary.is_(True), ApiKey.revoked_at.is_(None))
    ).first()
    if not primary_key or not primary_key.key_encrypted:
        raise HTTPException(status_code=500, detail="Primary API key missing")

    primary_key.last_used_at = datetime.now(timezone.utc)
    session.add(primary_key)
    session.commit()

    return {"user": UserRead.model_validate(user), "api_key": decrypt_api_key(primary_key.key_encrypted)}


@router.post("/logout")
def logout() -> dict:
    return {"message": "Logged out"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(require_user_by_api_key)) -> User:
    return current_user
