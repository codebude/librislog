import base64
import hashlib
import hmac
import re
import secrets

import bcrypt
from cryptography.fernet import Fernet
from fastapi import Depends, Header, HTTPException, Request, status
from passlib.exc import UnknownHashError
from passlib.context import CryptContext
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models import ApiKey, User, UserRole
from app.time_utils import utcnow


if not hasattr(bcrypt, "__about__"):
    class _BcryptAbout:
        __version__ = getattr(bcrypt, "__version__", "")


    bcrypt.__about__ = _BcryptAbout()  # type: ignore[attr-defined]

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
fallback_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

PASSWORD_COMPLEXITY_ERROR = (
    "Password must be at least 8 characters long and include uppercase, lowercase, number, and special character"
)

_UPPERCASE_RE = re.compile(r"[A-Z]")
_LOWERCASE_RE = re.compile(r"[a-z]")
_NUMBER_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9\s]")


def get_password_hash(password: str) -> str:
    try:
        return bcrypt_context.hash(password)
    except ValueError:
        return fallback_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    for context in (bcrypt_context, fallback_context):
        try:
            if context.verify(plain_password, hashed_password):
                return True
        except (UnknownHashError, ValueError):
            continue
    return False


def password_meets_complexity(password: str) -> bool:
    return (
        len(password) >= 8
        and _UPPERCASE_RE.search(password) is not None
        and _LOWERCASE_RE.search(password) is not None
        and _NUMBER_RE.search(password) is not None
        and _SPECIAL_RE.search(password) is not None
    )


def ensure_password_complexity(password: str) -> None:
    if not password_meets_complexity(password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PASSWORD_COMPLEXITY_ERROR)


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.api_key_encryption_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_api_key(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_api_key(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def hash_api_key(value: str) -> str:
    return hmac.new(settings.api_key_encryption_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_api_key() -> str:
    return f"lk_{secrets.token_urlsafe(32)}"


def get_api_key_prefix(api_key: str) -> str:
    return api_key[:12]


def require_user_by_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: Session = Depends(get_session),
) -> User:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    key_hash = hash_api_key(x_api_key)
    key = session.exec(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    ).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    user = session.get(User, key.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key user")

    key.last_used_at = utcnow()
    session.add(key)
    session.commit()
    return user


def require_user(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: Session = Depends(get_session),
) -> User:
    if x_api_key:
        return require_user_by_api_key(x_api_key=x_api_key, session=session)

    user_id = request.session.get("user_id")
    if user_id is not None:
        user = session.get(User, user_id)
        if user is not None:
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                csrf_token = request.session.get("csrf_token")
                if not csrf_token or not x_csrf_token or x_csrf_token != csrf_token:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
            return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


def start_browser_session(request: Request, user_id: int) -> None:
    request.session["user_id"] = user_id
    request.session["csrf_token"] = secrets.token_urlsafe(32)


def clear_browser_session(request: Request) -> None:
    request.session.clear()
