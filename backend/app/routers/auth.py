"""Authentication endpoints — login, logout, setup, session, CSRF, and password reset."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.auth import (
    clear_browser_session,
    ensure_password_complexity,
    generate_password_reset_token,
    get_password_hash,
    require_user,
    start_browser_session,
    verify_password_reset_token,
    verify_password,
)
from app.config import settings
from app.database import get_session
from app.email import send_password_reset_email
from app.models import User, UserRole, UserSettings
from app.schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SetupRequest,
    UserLogin,
    UserRead,
)
from app.time_utils import utcnow

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/setup-required")
def setup_required(session: Session = Depends(get_session)) -> dict:
    """Return whether initial admin setup is required."""
    admin = session.exec(select(User).where(User.role == UserRole.admin).limit(1)).first()
    return {"required": admin is None}


@router.post("/setup")
def setup(
    request: SetupRequest,
    http_request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Perform initial admin setup (creates the first admin user)."""
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
    assert user.id is not None

    session.add(UserSettings(user_id=user.id, language="en"))
    session.commit()

    start_browser_session(http_request, user.id, user.credentials_version)
    return {"user": UserRead.model_validate(user)}


@router.post("/login")
def login(
    credentials: UserLogin,
    http_request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Authenticate with email and password, starting a browser session."""
    user = session.exec(select(User).where(User.email == credentials.email)).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    assert user.id is not None

    start_browser_session(http_request, user.id, user.credentials_version)
    return {"user": UserRead.model_validate(user)}


@router.post("/logout")
def logout(http_request: Request) -> dict:
    """Clear the browser session."""
    clear_browser_session(http_request)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(require_user)) -> User:
    """Return the currently authenticated user."""
    return current_user


@router.get("/csrf")
def csrf_token(request: Request) -> dict:
    """Return the current CSRF token from the browser session."""
    token = request.session.get("csrf_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"csrf_token": token}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    """Send a password reset email to the user.

    Always returns 200 to prevent user enumeration.
    """
    user = session.exec(select(User).where(User.email == body.email)).first()
    if user and settings.mail_server:
        token = generate_password_reset_token(body.email, user.credentials_version)
        reset_url = f"{settings.public_app_url}/reset-password?token={token}"
        background_tasks.add_task(send_password_reset_email, body.email, reset_url, body.locale)
    return {"message": "If the email is registered, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    body: ResetPasswordRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Reset a user's password using a valid reset token."""
    payload = verify_password_reset_token(body.token, max_age=settings.password_reset_token_max_age)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    user = session.exec(select(User).where(User.email == payload["email"])).first()
    if not user or user.credentials_version != payload["credentials_version"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    ensure_password_complexity(body.password)
    user.hashed_password = get_password_hash(body.password)
    user.credentials_version += 1
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
    return {"message": "Password has been reset successfully"}
