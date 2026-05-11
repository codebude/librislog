# Multi-User Authentication & Authorization System - Implementation Plan

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Backend Auth Foundation](#phase-1-backend-auth-foundation)
3. [Phase 2: Database Migration & Data Association](#phase-2-database-migration--data-association)
4. [Phase 3: Backend Authorization](#phase-3-backend-authorization)
5. [Phase 4: Backend API Endpoints](#phase-4-backend-api-endpoints)
6. [Phase 5: Frontend Authentication UI](#phase-5-frontend-authentication-ui)
7. [Phase 6: Frontend User Profile & Settings Migration](#phase-6-frontend-user-profile--settings-migration)
8. [Phase 7: Testing & Documentation](#phase-7-testing--documentation)
9. [Rollout Strategy](#rollout-strategy)
10. [Risks & Mitigations](#risks--mitigations)

---

## Architecture Overview

### Goals
- Add multi-user authentication to LibrisLog
- Isolate book data per user (user_id foreign key on books table)
- Isolate cover storage per user (cover filenames include user scope)
- Role-based authorization: `admin` and `user` roles
- Setup flow: if no users exist, redirect to `/setup` to create first admin
- User management: admins can create/delete users (but not themselves)
- User profile: users can edit name, email, language preference
- API security: authorize protected endpoints via per-user API keys
- UI: User avatar bubble with dropdown (profile, logout)

### Tech Stack Additions
- **Password hashing**: `passlib[bcrypt]` (Python)
- **API key hashing**: HMAC-SHA256 (or SHA256 + server pepper) for secure key-at-rest
- **Frontend auth state**: Svelte stores + route guards

### Key Design Decisions
1. **API authorization strategy**: API key auth on protected endpoints
   - Each user has one main API key (bootstrap/login context) plus optional additional keys.
   - Client sends key in `X-API-Key` header.
   - DB stores additional keys as hash + prefix; plaintext shown once at creation.
   - Main app key is stored recoverably (encrypted-at-rest) so it can be re-read for app continuity when needed.
   - API key maps to user; user context is derived from key mapping.

2. **Password storage**: bcrypt hashing via `passlib`

3. **Setup page gating**:
   - Backend: `GET /auth/setup-required` returns `{"required": true/false}`
   - Frontend: Check on app load; redirect to `/setup` if true
   - Setup page backend: `POST /auth/setup` (only works if no users exist)

4. **Admin self-deletion prevention**:
   - Backend: `DELETE /users/{id}` checks if `current_user.id == id` → 403

5. **Language preference migration**:
   - Move from `localStorage` to `user_settings` table
   - On user login, fetch settings from backend and populate store
   - On settings change, persist to backend via `PATCH /profile/settings`

6. **Cover ownership safety**:
   - Persist user-scoped cover filenames (e.g., `<user_id>/<hash>.jpg` or `<user_id>__<hash>.jpg`).
   - Cover deletion checks must include owner user context; one user deleting a book must never remove another user's file.

### Data Model Changes

#### New Tables

**`users` table** (SQLModel):
```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    firstname: str
    lastname: str
    role: UserRole = Field(default=UserRole.user, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
```

**`user_settings` table** (SQLModel):
```python
class UserSettings(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    language: str = Field(default="en")  # 'en', 'de', etc.
    # Future: theme, timezone, etc.
```

**`UserRole` enum**:
```python
class UserRole(str, Enum):
    admin = "admin"
    user = "user"
```

**`api_keys` table** (SQLModel):
```python
class ApiKey(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key_prefix: str = Field(index=True)          # e.g. first 8 chars for display/debug
    key_hash: str | None = Field(default=None, unique=True, index=True)   # for additional keys
    key_encrypted: str | None = None                                       # for recoverable main key
    description: str | None = None               # user-provided note
    is_primary: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
```

#### Modified Tables

**`books` table**:
- Add `user_id: int = Field(foreign_key="user.id", index=True)`
- Migration challenge: existing books need a user_id → assign to first admin created during migration

---

## Refinement Addendum (API Keys + Cover Isolation)

This addendum supersedes any earlier cookie/JWT session notes in this plan.

### A) API Key Security Refinement
- All protected API endpoints use `X-API-Key` authentication.
- Login/setup flow returns an initial API key for the current user; frontend keeps it in in-memory auth store (optionally sessionStorage for refresh continuity).
- Users cannot view their existing primary key on profile.
- Profile page supports managing additional keys:
  - `POST /api/profile/api-keys` with `description`
  - `GET /api/profile/api-keys` (list metadata only: prefix, description, created_at, last_used_at, is_primary)
  - `DELETE /api/profile/api-keys/{id}` (revoke additional keys; primary revocation restricted)
- Key storage rules:
  - generate long random secret (`lk_...`), show once on creation,
  - additional keys: store hash only (`key_hash`),
  - primary key: store encrypted plaintext (`key_encrypted`) plus optional hash for lookup,
  - match request key by hash and update `last_used_at`.

### A.1) Clarification for Main Key Recoverability
- Since the frontend app itself uses the main key for API requests, the main key must be retrievable.
- Therefore:
  - primary key is encrypted-at-rest using server-side encryption key (e.g. `API_KEY_ENCRYPTION_KEY`),
  - backend can decrypt and reissue/show-to-user only in controlled flows (e.g. bootstrap/login recovery),
  - profile page still must not display the primary key by default.
- Additional user-created keys remain non-recoverable (hash-only) and are shown once on creation.

### B) Cover Filename Isolation Refinement
- Cover filenames/hashes must include `user_id` namespace.
- Cover dedup can still happen per user, but never globally across users.
- File deletion logic checks ownership scope before deleting from disk.

### C) Endpoint/Auth Dependency Refinement
- Replace `get_current_user` cookie dependency with API-key dependency.
- Add `require_api_key_user` and `require_admin` wrappers.
- Keep setup gating unchanged:
  - `/setup` only if no admin exists,
  - `/setup` blocked after first admin creation.

### D) Migration Refinement
- Add `api_keys` table in migration set.
- Create primary API key for bootstrap admin during setup (and for migrated default admin path).
- Backfill/normalize existing cover paths to user-scoped names where needed.

### E) UI Refinement
- Profile page includes new API keys section:
  - create key with description,
  - copy-once display for new key,
  - list/revoke additional keys,
  - primary key hidden (only metadata row, no plaintext).

---

## Phase 1: Backend Auth Foundation

**Goal**: Establish authentication primitives (password hashing, JWT generation, user model).

### 1.1 Install Dependencies

Add to `backend/pyproject.toml`:
```toml
dependencies = [
    # ... existing ...
    "passlib[bcrypt]>=1.7.4",
    "python-jose[cryptography]>=3.3.0",
    "python-multipart>=0.0.28",  # already present, needed for form data
]
```

Run: `uv sync` in backend directory.

### 1.2 Create User Models

**File**: `backend/app/models.py` (append)

```python
from enum import Enum

class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, sa_column_kwargs={"collation": "NOCASE"})  # case-insensitive email
    firstname: str
    lastname: str
    role: UserRole = Field(default=UserRole.user, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class UserSettings(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    language: str = Field(default="en", max_length=10)
```

### 1.3 Create User Schemas

**File**: `backend/app/schemas.py` (append)

```python
from app.models import UserRole

# ── Auth ──────────────────────────────────────────────────────────────────────

class UserLogin(SQLModel):
    email: str
    password: str


class UserCreate(SQLModel):
    email: str
    firstname: str
    lastname: str
    password: str
    role: UserRole = UserRole.user


class UserRead(SQLModel):
    id: int
    email: str
    firstname: str
    lastname: str
    role: UserRole
    created_at: datetime


class UserUpdate(SQLModel):
    firstname: str | None = None
    lastname: str | None = None
    email: str | None = None
    password: str | None = None  # if provided, will be hashed and updated


class UserSettingsRead(SQLModel):
    user_id: int
    language: str


class UserSettingsUpdate(SQLModel):
    language: str | None = None


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"


class SetupRequest(SQLModel):
    email: str
    firstname: str
    lastname: str
    password: str
```

### 1.4 Password Hashing Utility

**File**: `backend/app/auth.py` (new)

```python
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
```

### 1.5 Update Config

**File**: `backend/app/config.py`

Add:
```python
class Settings(BaseSettings):
    # ... existing ...
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"  # Used for JWT signing
    access_token_expire_hours: int = 24
```

**Important**: Update `.env.example` to document `SECRET_KEY`.

---

## Phase 2: Database Migration & Data Association

**Goal**: Create alembic migration to add `users`, `user_settings` tables, add `user_id` to `books`, migrate existing data.

### 2.1 Create Alembic Migration

Run:
```bash
cd backend
uv run alembic revision -m "add_users_and_multi_user_support"
```

### 2.2 Write Migration Logic

**File**: `backend/alembic/versions/<revision>_add_users_and_multi_user_support.py`

**Upgrade**:
1. Create `users` table
2. Create `user_settings` table
3. Add `user_id` column to `books` table (nullable initially)
4. **Data migration**: Check if any users exist; if not, create a default admin:
   ```python
   # Check if users table is empty
   conn = op.get_bind()
   result = conn.execute(sa.text("SELECT COUNT(*) FROM users"))
   count = result.scalar()
   if count == 0:
       # Create default admin
       from app.auth import get_password_hash
       hashed_pw = get_password_hash("admin")  # Default password, user must change
       now = datetime.now(timezone.utc)
       conn.execute(sa.text("""
           INSERT INTO users (email, firstname, lastname, role, hashed_password, created_at, updated_at)
           VALUES (:email, :firstname, :lastname, :role, :hashed_pw, :now, :now)
       """), {"email": "admin@librislog.local", "firstname": "Admin", "lastname": "User", "role": "admin", "hashed_pw": hashed_pw, "now": now})
       
       # Get the admin user id
       result = conn.execute(sa.text("SELECT id FROM users WHERE email = :email"), {"email": "admin@librislog.local"})
       admin_id = result.scalar()
       
       # Update all existing books to belong to this admin
       conn.execute(sa.text("UPDATE books SET user_id = :admin_id"), {"admin_id": admin_id})
       
       # Create default user settings
       conn.execute(sa.text("INSERT INTO user_settings (user_id, language) VALUES (:user_id, 'en')"), {"user_id": admin_id})
   ```
5. Make `user_id` NOT NULL on `books` table (after data migration ensures all books have a user_id)
6. Create foreign key constraint on `books.user_id` → `users.id`

**Downgrade**:
1. Drop foreign key on `books.user_id`
2. Drop `user_id` column from `books`
3. Drop `user_settings` table
4. Drop `users` table

**Implementation notes**:
- Use raw SQL for data migration (not ORM) to avoid import issues
- Hash default password using `app.auth.get_password_hash`
- Log default admin credentials prominently in migration output

### 2.3 Apply Migration

```bash
cd backend
uv run alembic upgrade head
```

**Post-migration verification**:
- Check that `users` table has one admin user
- Check that all books have `user_id` set
- Check that `user_settings` table has one record

---

## Phase 3: Backend Authorization

**Goal**: Implement authentication dependency injection, role checks, and data isolation.

### 3.1 Authentication Dependencies

**File**: `backend/app/auth.py` (append)

```python
from fastapi import Cookie, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, UserRole


def get_current_user(
    access_token: str | None = Cookie(default=None, alias="access_token"),
    session: Session = Depends(get_session),
) -> User:
    """Extract and validate JWT from cookie, return current user."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    payload = decode_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    user_id: int | None = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role."""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
```

### 3.2 Update Book Endpoints for Data Isolation

**File**: `backend/app/routers/books.py`

**Changes**:
1. Import `get_current_user` from `app.auth`
2. Add `current_user: User = Depends(get_current_user)` to all endpoints
3. Filter queries by `user_id`:
   ```python
   # Example: list_books
   def list_books(
       status: Optional[ReadingStatus] = Query(default=None),
       # ... other params ...
       current_user: User = Depends(get_current_user),
       session: Session = Depends(get_session),
   ) -> List[Book]:
       statement = select(Book).where(Book.user_id == current_user.id)
       # ... rest of filtering ...
   ```
4. Ensure `create_book` sets `user_id`:
   ```python
   book_data["user_id"] = current_user.id
   ```
5. Ensure `get_book`, `update_book`, `delete_book` verify ownership:
   ```python
   book = session.get(Book, book_id)
   if not book or book.user_id != current_user.id:
       raise HTTPException(status_code=404, detail="Book not found")
   ```

**Testing impact**: All existing tests will break (401 Unauthorized). Need to add auth fixture.

### 3.3 Update Import Endpoints

**File**: `backend/app/routers/import_.py`

- Add `current_user: User = Depends(get_current_user)` to all endpoints
- Filter imported books by `user_id`
- Set `user_id` when persisting imported books

### 3.4 Update Cover Endpoints (if needed)

**File**: `backend/app/routers/covers.py`

- If covers are user-specific, add `current_user` dependency
- Otherwise, covers can remain unauthenticated (served by filename)

**Decision**: Keep covers unauthenticated for simplicity (filename is UUID-based, hard to guess). If security is critical, add auth and verify user owns a book using that cover.

---

## Phase 4: Backend API Endpoints

**Goal**: Implement `/auth/*` and `/users/*` endpoints.

### 4.1 Auth Router

**File**: `backend/app/routers/auth.py` (new)

```python
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status, Cookie
from sqlmodel import Session, select

from app.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.config import settings
from app.database import get_session
from app.models import User, UserRole, UserSettings
from app.schemas import SetupRequest, TokenResponse, UserLogin, UserRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/setup-required")
def setup_required(session: Session = Depends(get_session)) -> dict:
    """Check if initial setup is required (no users exist)."""
    statement = select(User).where(User.role == UserRole.admin).limit(1)
    admin_exists = session.exec(statement).first() is not None
    return {"required": not admin_exists}


@router.post("/setup", response_model=UserRead, status_code=201)
def setup(request: SetupRequest, session: Session = Depends(get_session)) -> User:
    """Create the first admin user. Only works if no admin exists."""
    statement = select(User).where(User.role == UserRole.admin).limit(1)
    admin_exists = session.exec(statement).first() is not None
    if admin_exists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup already completed",
        )
    
    # Check if email already exists (shouldn't happen, but defensive)
    existing = session.exec(select(User).where(User.email == request.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    user = User(
        email=request.email,
        firstname=request.firstname,
        lastname=request.lastname,
        role=UserRole.admin,
        hashed_password=get_password_hash(request.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create default user settings
    settings_record = UserSettings(user_id=user.id, language="en")
    session.add(settings_record)
    session.commit()
    
    logger.info("Setup completed: created admin user %s", user.email)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLogin,
    response: Response,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Authenticate user and return JWT token in cookie."""
    user = session.exec(select(User).where(User.email == credentials.email)).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    token_data = {
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value,
    }
    expires_delta = timedelta(hours=settings.access_token_expire_hours)
    access_token = create_access_token(token_data, expires_delta)
    
    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,  # True in production (HTTPS only)
        samesite="lax",
        max_age=settings.access_token_expire_hours * 3600,
    )
    
    logger.info("User %s logged in", user.email)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear authentication cookie."""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserRead)
def get_current_user_info(current_user: User = Depends(get_current_user)) -> User:
    """Return current authenticated user's info."""
    return current_user
```

**Config update** (`backend/app/config.py`):
```python
class Settings(BaseSettings):
    # ... existing ...
    cookie_secure: bool = False  # Set to True in production (requires HTTPS)
```

### 4.2 Users Router (Admin-only CRUD)

**File**: `backend/app/routers/users.py` (new)

```python
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_password_hash, require_admin, get_current_user
from app.database import get_session
from app.models import User, UserRole, UserSettings
from app.schemas import UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
def list_users(session: Session = Depends(get_session)) -> list[User]:
    """List all users (admin only)."""
    users = session.exec(select(User).order_by(User.created_at)).all()
    return list(users)


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    user_in: UserCreate,
    session: Session = Depends(get_session),
) -> User:
    """Create a new user (admin only)."""
    # Check if email already exists
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    user = User(
        email=user_in.email,
        firstname=user_in.firstname,
        lastname=user_in.lastname,
        role=user_in.role,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create default user settings
    settings_record = UserSettings(user_id=user.id, language="en")
    session.add(settings_record)
    session.commit()
    
    logger.info("Created user: %s (role=%s)", user.email, user.role)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)) -> User:
    """Get user by ID (admin only)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    session: Session = Depends(get_session),
) -> User:
    """Update user (admin only)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.model_dump(exclude_unset=True)
    
    # If email is being changed, check uniqueness
    if "email" in update_data and update_data["email"] != user.email:
        existing = session.exec(select(User).where(User.email == update_data["email"])).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
    
    # If password is being changed, hash it
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    user.sqlmodel_update(update_data)
    session.add(user)
    session.commit()
    session.refresh(user)
    
    logger.info("Updated user: %s", user.email)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete user (admin only). Admins cannot delete themselves."""
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete your own account",
        )
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete user's settings
    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user_id)).first()
    if settings:
        session.delete(settings)
    
    # Note: books are NOT deleted (add ON DELETE CASCADE if desired, or soft-delete user)
    # Current design: Books remain orphaned or handle via migration
    # Recommendation: Add ON DELETE RESTRICT to prevent deletion if user has books
    
    session.delete(user)
    session.commit()
    logger.info("Deleted user: %s", user.email)
```

**Design decision**: Should deleting a user delete their books?
- **Option A**: ON DELETE CASCADE (books are deleted)
- **Option B**: ON DELETE RESTRICT (prevent deletion if user has books)
- **Recommendation**: Option B for safety. Admin must reassign or delete books first.

### 4.3 Profile Router (User self-management)

**File**: `backend/app/routers/profile.py` (new)

```python
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user, get_password_hash
from app.database import get_session
from app.models import User, UserSettings
from app.schemas import UserRead, UserSettingsRead, UserSettingsUpdate, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=UserRead)
def get_profile(current_user: User = Depends(get_current_user)) -> User:
    """Get current user's profile."""
    return current_user


@router.patch("", response_model=UserRead)
def update_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    """Update current user's profile."""
    update_data = user_in.model_dump(exclude_unset=True)
    
    # If email is being changed, check uniqueness
    if "email" in update_data and update_data["email"] != current_user.email:
        existing = session.exec(select(User).where(User.email == update_data["email"])).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
    
    # If password is being changed, hash it
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    current_user.sqlmodel_update(update_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    logger.info("User %s updated profile", current_user.email)
    return current_user


@router.get("/settings", response_model=UserSettingsRead)
def get_user_settings(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserSettings:
    """Get current user's settings."""
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    ).first()
    
    if not settings:
        # Create default settings if not exist
        settings = UserSettings(user_id=current_user.id, language="en")
        session.add(settings)
        session.commit()
        session.refresh(settings)
    
    return settings


@router.patch("/settings", response_model=UserSettingsRead)
def update_user_settings(
    settings_in: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserSettings:
    """Update current user's settings."""
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    ).first()
    
    if not settings:
        # Create if not exist
        settings = UserSettings(user_id=current_user.id, language="en")
        session.add(settings)
    
    update_data = settings_in.model_dump(exclude_unset=True)
    settings.sqlmodel_update(update_data)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    logger.info("User %s updated settings: %s", current_user.email, update_data)
    return settings
```

### 4.4 Register Routers

**File**: `backend/app/main.py`

Import and include routers:
```python
from app.routers import auth, books, covers, import_, profile, users

# ... existing setup ...

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profile.router)
app.include_router(books.router)
app.include_router(import_.router)
app.include_router(covers.router)
```

---

## Phase 5: Frontend Authentication UI

**Goal**: Build login, setup, and profile pages; add route guards; handle auth state.

### 5.1 Auth State Management

**File**: `frontend/src/lib/stores/auth.ts` (new)

```typescript
import { writable, derived, get } from 'svelte/store';
import type { UserRead } from '$lib/types';
import { api } from '$lib/api';

interface AuthState {
    user: UserRead | null;
    loading: boolean;
}

function createAuthStore() {
    const { subscribe, set, update } = writable<AuthState>({
        user: null,
        loading: true,
    });

    return {
        subscribe,
        async init() {
            try {
                const user = await api.auth.me();
                set({ user, loading: false });
            } catch {
                set({ user: null, loading: false });
            }
        },
        async login(email: string, password: string) {
            await api.auth.login({ email, password });
            const user = await api.auth.me();
            set({ user, loading: false });
        },
        async logout() {
            await api.auth.logout();
            set({ user: null, loading: false });
        },
        clear() {
            set({ user: null, loading: false });
        },
    };
}

export const auth = createAuthStore();

export const isAuthenticated = derived(auth, ($auth) => !!$auth.user);
export const isAdmin = derived(auth, ($auth) => $auth.user?.role === 'admin');
```

### 5.2 API Client Updates

**File**: `frontend/src/lib/api.ts` (update)

Add auth API methods:
```typescript
// Add to types (or import from generated types)
interface UserRead {
    id: number;
    email: string;
    firstname: string;
    lastname: string;
    role: 'admin' | 'user';
    created_at: string;
}

interface UserSettingsRead {
    user_id: number;
    language: string;
}

// Add to api object
export const api = {
    // ... existing books, import, covers ...
    
    auth: {
        setupRequired: (): Promise<{ required: boolean }> =>
            http.get('/api/auth/setup-required'),
        
        setup: (data: { email: string; firstname: string; lastname: string; password: string }): Promise<UserRead> =>
            http.post('/api/auth/setup', data),
        
        login: (credentials: { email: string; password: string }): Promise<{ access_token: string; token_type: string }> =>
            http.post('/api/auth/login', credentials),
        
        logout: (): Promise<void> =>
            http.post('/api/auth/logout', {}),
        
        me: (): Promise<UserRead> =>
            http.get('/api/auth/me'),
    },
    
    profile: {
        get: (): Promise<UserRead> =>
            http.get('/api/profile'),
        
        update: (data: { firstname?: string; lastname?: string; email?: string; password?: string }): Promise<UserRead> =>
            http.patch('/api/profile', data),
        
        getSettings: (): Promise<UserSettingsRead> =>
            http.get('/api/profile/settings'),
        
        updateSettings: (data: { language?: string }): Promise<UserSettingsRead> =>
            http.patch('/api/profile/settings', data),
    },
    
    users: {
        list: (): Promise<UserRead[]> =>
            http.get('/api/users'),
        
        create: (data: { email: string; firstname: string; lastname: string; password: string; role: 'admin' | 'user' }): Promise<UserRead> =>
            http.post('/api/users', data),
        
        get: (id: number): Promise<UserRead> =>
            http.get(`/api/users/${id}`),
        
        update: (id: number, data: { firstname?: string; lastname?: string; email?: string; password?: string }): Promise<UserRead> =>
            http.patch(`/api/users/${id}`, data),
        
        delete: (id: number): Promise<void> =>
            http.delete(`/api/users/${id}`),
    },
};
```

**HTTP client update**: Handle 401 errors globally (redirect to login).

```typescript
async function request<T>(method: string, url: string, body?: any): Promise<T> {
    const options: RequestInit = {
        method,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',  // Send cookies
    };
    if (body) options.body = JSON.stringify(body);

    const res = await fetch(`${API_BASE_URL}${url}`, options);
    
    if (res.status === 401) {
        // Redirect to login (or emit event for router to handle)
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    
    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${res.status}`);
    }
    
    if (res.status === 204) return undefined as T;
    return res.json();
}
```

### 5.3 Login Page

**File**: `frontend/src/routes/login/+page.svelte` (new)

```svelte
<script lang="ts">
    import { goto } from '$app/navigation';
    import { auth } from '$lib/stores/auth';
    import { _ } from '$lib/i18n';
    
    let email = $state('');
    let password = $state('');
    let error = $state('');
    let loading = $state(false);
    
    async function handleLogin() {
        error = '';
        loading = true;
        try {
            await auth.login(email, password);
            goto('/');
        } catch (err: any) {
            error = err.message || 'Login failed';
        } finally {
            loading = false;
        }
    }
</script>

<div class="min-h-screen bg-base-200 flex items-center justify-center p-4">
    <div class="card bg-base-100 shadow-xl w-full max-w-md">
        <div class="card-body">
            <h1 class="text-2xl font-bold text-center mb-4">{$_('auth.login')}</h1>
            
            {#if error}
                <div class="alert alert-error mb-4">
                    <span>{error}</span>
                </div>
            {/if}
            
            <form onsubmit={handleLogin}>
                <div class="form-control mb-4">
                    <label class="label" for="email">
                        <span class="label-text">{$_('auth.email')}</span>
                    </label>
                    <input
                        id="email"
                        type="email"
                        bind:value={email}
                        class="input input-bordered"
                        required
                        disabled={loading}
                    />
                </div>
                
                <div class="form-control mb-6">
                    <label class="label" for="password">
                        <span class="label-text">{$_('auth.password')}</span>
                    </label>
                    <input
                        id="password"
                        type="password"
                        bind:value={password}
                        class="input input-bordered"
                        required
                        disabled={loading}
                    />
                </div>
                
                <button type="submit" class="btn btn-primary w-full" disabled={loading}>
                    {#if loading}
                        <span class="loading loading-spinner"></span>
                    {/if}
                    {$_('auth.login')}
                </button>
            </form>
        </div>
    </div>
</div>
```

### 5.4 Setup Page

**File**: `frontend/src/routes/setup/+page.svelte` (new)

```svelte
<script lang="ts">
    import { goto } from '$app/navigation';
    import { onMount } from 'svelte';
    import { api } from '$lib/api';
    import { auth } from '$lib/stores/auth';
    import { _ } from '$lib/i18n';
    
    let firstname = $state('');
    let lastname = $state('');
    let email = $state('');
    let password = $state('');
    let passwordConfirm = $state('');
    let error = $state('');
    let loading = $state(false);
    let setupRequired = $state<boolean | null>(null);
    
    onMount(async () => {
        const { required } = await api.auth.setupRequired();
        setupRequired = required;
        if (!required) {
            // Setup already done, redirect to login
            goto('/login');
        }
    });
    
    async function handleSetup() {
        error = '';
        
        if (password !== passwordConfirm) {
            error = 'Passwords do not match';
            return;
        }
        
        loading = true;
        try {
            await api.auth.setup({ email, firstname, lastname, password });
            // Auto-login
            await auth.login(email, password);
            goto('/');
        } catch (err: any) {
            error = err.message || 'Setup failed';
        } finally {
            loading = false;
        }
    }
</script>

{#if setupRequired === null}
    <div class="min-h-screen bg-base-200 flex items-center justify-center">
        <span class="loading loading-spinner loading-lg"></span>
    </div>
{:else if setupRequired}
    <div class="min-h-screen bg-base-200 flex items-center justify-center p-4">
        <div class="card bg-base-100 shadow-xl w-full max-w-md">
            <div class="card-body">
                <h1 class="text-2xl font-bold text-center mb-2">{$_('auth.setup_title')}</h1>
                <p class="text-sm text-base-content/70 text-center mb-4">
                    {$_('auth.setup_description')}
                </p>
                
                {#if error}
                    <div class="alert alert-error mb-4">
                        <span>{error}</span>
                    </div>
                {/if}
                
                <form onsubmit={handleSetup}>
                    <div class="form-control mb-3">
                        <label class="label" for="firstname">
                            <span class="label-text">{$_('auth.firstname')}</span>
                        </label>
                        <input
                            id="firstname"
                            type="text"
                            bind:value={firstname}
                            class="input input-bordered"
                            required
                            disabled={loading}
                        />
                    </div>
                    
                    <div class="form-control mb-3">
                        <label class="label" for="lastname">
                            <span class="label-text">{$_('auth.lastname')}</span>
                        </label>
                        <input
                            id="lastname"
                            type="text"
                            bind:value={lastname}
                            class="input input-bordered"
                            required
                            disabled={loading}
                        />
                    </div>
                    
                    <div class="form-control mb-3">
                        <label class="label" for="email">
                            <span class="label-text">{$_('auth.email')}</span>
                        </label>
                        <input
                            id="email"
                            type="email"
                            bind:value={email}
                            class="input input-bordered"
                            required
                            disabled={loading}
                        />
                    </div>
                    
                    <div class="form-control mb-3">
                        <label class="label" for="password">
                            <span class="label-text">{$_('auth.password')}</span>
                        </label>
                        <input
                            id="password"
                            type="password"
                            bind:value={password}
                            class="input input-bordered"
                            required
                            disabled={loading}
                        />
                    </div>
                    
                    <div class="form-control mb-6">
                        <label class="label" for="password-confirm">
                            <span class="label-text">{$_('auth.password_confirm')}</span>
                        </label>
                        <input
                            id="password-confirm"
                            type="password"
                            bind:value={passwordConfirm}
                            class="input input-bordered"
                            required
                            disabled={loading}
                        />
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-full" disabled={loading}>
                        {#if loading}
                            <span class="loading loading-spinner"></span>
                        {/if}
                        {$_('auth.setup_submit')}
                    </button>
                </form>
            </div>
        </div>
    </div>
{/if}
```

### 5.5 Route Guards (Layout)

**File**: `frontend/src/routes/+layout.svelte` (update)

Add auth initialization and redirect logic:

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { auth, isAuthenticated } from '$lib/stores/auth';
    import { api } from '$lib/api';
    
    // ... existing imports ...
    
    let authReady = $state(false);
    
    onMount(async () => {
        // Check if setup is required
        const { required } = await api.auth.setupRequired();
        if (required && $page.url.pathname !== '/setup') {
            goto('/setup');
            return;
        }
        
        // Initialize auth
        await auth.init();
        authReady = true;
        
        // Redirect to login if not authenticated (unless on public routes)
        if (!$isAuthenticated && $page.url.pathname !== '/login' && $page.url.pathname !== '/setup') {
            goto('/login');
        }
    });
</script>

{#if !authReady}
    <div class="min-h-screen bg-base-200 flex items-center justify-center">
        <span class="loading loading-spinner loading-lg"></span>
    </div>
{:else}
    <!-- existing layout -->
{/if}
```

**Note**: This is a simplified guard. For production, consider using SvelteKit's `load` functions or hooks for server-side redirects.

---

## Phase 6: Frontend User Profile & Settings Migration

**Goal**: Add user avatar dropdown, profile page, migrate language settings to backend.

### 6.1 User Avatar Bubble Component

**File**: `frontend/src/lib/components/UserMenu.svelte` (new)

```svelte
<script lang="ts">
    import { auth } from '$lib/stores/auth';
    import { _ } from '$lib/i18n';
    
    const user = $derived($auth.user);
    const initials = $derived(
        user ? `${user.firstname.charAt(0)}${user.lastname.charAt(0)}`.toUpperCase() : ''
    );
    
    let dropdownOpen = $state(false);
    
    function toggleDropdown() {
        dropdownOpen = !dropdownOpen;
    }
    
    function closeDropdown() {
        dropdownOpen = false;
    }
    
    async function handleLogout() {
        await auth.logout();
        window.location.href = '/login';
    }
</script>

<div class="relative">
    <button
        class="btn btn-circle btn-ghost"
        onclick={toggleDropdown}
        aria-label="User menu"
    >
        <div class="avatar placeholder">
            <div class="bg-primary text-primary-content rounded-full w-10">
                <span class="text-sm">{initials}</span>
            </div>
        </div>
    </button>
    
    {#if dropdownOpen}
        <div
            class="absolute right-0 mt-2 w-48 bg-base-100 rounded-lg shadow-lg border border-base-200 z-50"
            onclick={closeDropdown}
        >
            <ul class="menu p-2 gap-1">
                <li>
                    <a href="/profile" class="flex items-center gap-2">
                        <span>👤</span>{$_('user.profile')}
                    </a>
                </li>
                <li>
                    <button onclick={handleLogout} class="flex items-center gap-2">
                        <span>🚪</span>{$_('user.logout')}
                    </button>
                </li>
            </ul>
        </div>
    {/if}
</div>
```

### 6.2 Add User Menu to Layout

**File**: `frontend/src/routes/+layout.svelte` (update)

Import and add `<UserMenu />` to header:

```svelte
<script lang="ts">
    import UserMenu from '$lib/components/UserMenu.svelte';
    // ... existing imports ...
</script>

<!-- Desktop sidebar -->
<aside class="...">
    <!-- ... existing nav ... -->
    <UserMenu />
</aside>

<!-- Mobile header -->
<header class="...">
    <span class="...">{$_('app.title')}</span>
    <div class="flex items-center gap-2">
        <button class="btn btn-primary btn-sm" onclick={() => (addBookOpen = true)}>+ {$_('app.add')}</button>
        <UserMenu />
    </div>
</header>
```

### 6.3 Profile Page

**File**: `frontend/src/routes/profile/+page.svelte` (new)

```svelte
<script lang="ts">
    import { auth } from '$lib/stores/auth';
    import { api } from '$lib/api';
    import { _, setLocale, locale, SUPPORTED_LOCALES, type AppLocale } from '$lib/i18n';
    import { onMount } from 'svelte';
    
    const user = $derived($auth.user!);
    
    let firstname = $state(user.firstname);
    let lastname = $state(user.lastname);
    let email = $state(user.email);
    let password = $state('');
    let passwordConfirm = $state('');
    
    let settings = $state<{ language: string } | null>(null);
    let saving = $state(false);
    let error = $state('');
    let success = $state('');
    
    onMount(async () => {
        settings = await api.profile.getSettings();
    });
    
    async function handleSaveProfile() {
        error = '';
        success = '';
        saving = true;
        
        try {
            const updates: any = {};
            if (firstname !== user.firstname) updates.firstname = firstname;
            if (lastname !== user.lastname) updates.lastname = lastname;
            if (email !== user.email) updates.email = email;
            if (password) {
                if (password !== passwordConfirm) {
                    error = 'Passwords do not match';
                    saving = false;
                    return;
                }
                updates.password = password;
            }
            
            if (Object.keys(updates).length > 0) {
                await api.profile.update(updates);
                await auth.init();  // Refresh user data
                success = 'Profile updated successfully';
                password = '';
                passwordConfirm = '';
            }
        } catch (err: any) {
            error = err.message || 'Failed to update profile';
        } finally {
            saving = false;
        }
    }
    
    async function handleLanguageChange(event: Event) {
        const newLang = (event.currentTarget as HTMLSelectElement).value as AppLocale;
        if (!SUPPORTED_LOCALES.includes(newLang)) return;
        
        try {
            await api.profile.updateSettings({ language: newLang });
            setLocale(newLang);
            success = 'Language updated';
        } catch (err: any) {
            error = err.message || 'Failed to update language';
        }
    }
</script>

<div class="max-w-2xl mx-auto flex flex-col gap-6">
    <h1 class="text-2xl font-bold">{$_('user.profile')}</h1>
    
    {#if error}
        <div class="alert alert-error">
            <span>{error}</span>
        </div>
    {/if}
    
    {#if success}
        <div class="alert alert-success">
            <span>{success}</span>
        </div>
    {/if}
    
    <div class="card bg-base-100 shadow-sm border border-base-200">
        <div class="card-body">
            <h2 class="text-lg font-semibold mb-4">{$_('user.profile_info')}</h2>
            
            <form onsubmit={handleSaveProfile}>
                <div class="form-control mb-3">
                    <label class="label" for="firstname">
                        <span class="label-text">{$_('auth.firstname')}</span>
                    </label>
                    <input
                        id="firstname"
                        type="text"
                        bind:value={firstname}
                        class="input input-bordered"
                        required
                        disabled={saving}
                    />
                </div>
                
                <div class="form-control mb-3">
                    <label class="label" for="lastname">
                        <span class="label-text">{$_('auth.lastname')}</span>
                    </label>
                    <input
                        id="lastname"
                        type="text"
                        bind:value={lastname}
                        class="input input-bordered"
                        required
                        disabled={saving}
                    />
                </div>
                
                <div class="form-control mb-4">
                    <label class="label" for="email">
                        <span class="label-text">{$_('auth.email')}</span>
                    </label>
                    <input
                        id="email"
                        type="email"
                        bind:value={email}
                        class="input input-bordered"
                        required
                        disabled={saving}
                    />
                </div>
                
                <div class="divider">{$_('user.change_password')}</div>
                
                <div class="form-control mb-3">
                    <label class="label" for="password">
                        <span class="label-text">{$_('auth.new_password')}</span>
                    </label>
                    <input
                        id="password"
                        type="password"
                        bind:value={password}
                        class="input input-bordered"
                        placeholder="Leave blank to keep current"
                        disabled={saving}
                    />
                </div>
                
                <div class="form-control mb-6">
                    <label class="label" for="password-confirm">
                        <span class="label-text">{$_('auth.password_confirm')}</span>
                    </label>
                    <input
                        id="password-confirm"
                        type="password"
                        bind:value={passwordConfirm}
                        class="input input-bordered"
                        disabled={saving}
                    />
                </div>
                
                <button type="submit" class="btn btn-primary" disabled={saving}>
                    {#if saving}
                        <span class="loading loading-spinner"></span>
                    {/if}
                    {$_('user.save_profile')}
                </button>
            </form>
        </div>
    </div>
    
    {#if settings}
        <div class="card bg-base-100 shadow-sm border border-base-200">
            <div class="card-body">
                <h2 class="text-lg font-semibold mb-4">{$_('settings.languageTitle')}</h2>
                <label class="form-control">
                    <span class="label label-text">{$_('settings.languageTitle')}</span>
                    <select class="select select-bordered" value={settings.language} onchange={handleLanguageChange}>
                        {#each SUPPORTED_LOCALES as code}
                            <option value={code}>{$_(`languages.${code}`)}</option>
                        {/each}
                    </select>
                </label>
            </div>
        </div>
    {/if}
</div>
```

### 6.4 Update i18n to Load from Backend

**File**: `frontend/src/lib/i18n/index.ts` (update)

On setup, fetch language preference from backend instead of localStorage:

```typescript
export async function setupI18n(preloadedLanguage?: string) {
    if (initialized) {
        await waitLocale();
        return;
    }

    // If user is authenticated, fetch language from backend
    // Otherwise, fall back to localStorage or default
    const initialLocale = preloadedLanguage ?? getStoredLocale() ?? configuredDefaultLocale;

    init({
        fallbackLocale: 'en',
        initialLocale
    });

    initialized = true;
    await waitLocale();
}
```

**Usage in `+layout.svelte`**:
```svelte
onMount(async () => {
    // ... setup/auth checks ...
    await auth.init();
    
    if ($isAuthenticated) {
        const settings = await api.profile.getSettings();
        await setupI18n(settings.language);
    } else {
        await setupI18n();
    }
    
    // ... rest of layout ...
});
```

### 6.5 Translation Keys

Add to `frontend/src/lib/i18n/locales/en.json`:
```json
{
    "auth": {
        "login": "Login",
        "email": "Email",
        "password": "Password",
        "firstname": "First Name",
        "lastname": "Last Name",
        "password_confirm": "Confirm Password",
        "new_password": "New Password",
        "setup_title": "Initial Setup",
        "setup_description": "Create your admin account to get started.",
        "setup_submit": "Create Admin Account"
    },
    "user": {
        "profile": "Profile",
        "logout": "Logout",
        "profile_info": "Profile Information",
        "change_password": "Change Password",
        "save_profile": "Save Profile"
    }
}
```

(Repeat for `de.json` with German translations.)

---

## Phase 7: Testing & Documentation

### 7.1 Backend Tests

#### 7.1.1 Auth Fixtures

**File**: `backend/tests/conftest.py` (update)

```python
import pytest
from app.models import User, UserRole, UserSettings
from app.auth import get_password_hash

@pytest.fixture
def admin_user(session):
    """Create an admin user for testing."""
    user = User(
        email="admin@test.com",
        firstname="Admin",
        lastname="User",
        role=UserRole.admin,
        hashed_password=get_password_hash("adminpass"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    settings = UserSettings(user_id=user.id, language="en")
    session.add(settings)
    session.commit()
    
    return user


@pytest.fixture
def regular_user(session):
    """Create a regular user for testing."""
    user = User(
        email="user@test.com",
        firstname="Regular",
        lastname="User",
        role=UserRole.user,
        hashed_password=get_password_hash("userpass"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    settings = UserSettings(user_id=user.id, language="en")
    session.add(settings)
    session.commit()
    
    return user


@pytest.fixture
def auth_headers_admin(admin_user):
    """Generate auth headers for admin user."""
    from app.auth import create_access_token
    token = create_access_token({"user_id": admin_user.id, "email": admin_user.email, "role": admin_user.role.value})
    return {"Cookie": f"access_token={token}"}


@pytest.fixture
def auth_headers_user(regular_user):
    """Generate auth headers for regular user."""
    from app.auth import create_access_token
    token = create_access_token({"user_id": regular_user.id, "email": regular_user.email, "role": regular_user.role.value})
    return {"Cookie": f"access_token={token}"}
```

#### 7.1.2 Auth Endpoint Tests

**File**: `backend/tests/test_auth.py` (new)

```python
from fastapi.testclient import TestClient

def test_setup_required_when_no_users(client: TestClient):
    resp = client.get("/api/auth/setup-required")
    assert resp.status_code == 200
    assert resp.json()["required"] is True


def test_setup_creates_admin_user(client: TestClient):
    resp = client.post("/api/auth/setup", json={
        "email": "admin@example.com",
        "firstname": "Admin",
        "lastname": "User",
        "password": "securepass",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "admin@example.com"
    assert data["role"] == "admin"


def test_setup_fails_when_admin_exists(client: TestClient, admin_user):
    resp = client.post("/api/auth/setup", json={
        "email": "another@example.com",
        "firstname": "Another",
        "lastname": "Admin",
        "password": "pass",
    })
    assert resp.status_code == 403


def test_login_success(client: TestClient, admin_user):
    resp = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "adminpass",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "access_token" in resp.cookies


def test_login_invalid_credentials(client: TestClient, admin_user):
    resp = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


def test_logout(client: TestClient, auth_headers_admin):
    resp = client.post("/api/auth/logout", headers=auth_headers_admin)
    assert resp.status_code == 200
    # In real test, verify cookie is cleared


def test_get_me(client: TestClient, admin_user, auth_headers_admin):
    resp = client.get("/api/auth/me", headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@test.com"


def test_get_me_unauthorized(client: TestClient):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
```

#### 7.1.3 Book Ownership Tests

**File**: `backend/tests/test_books.py` (update)

Update existing tests to use auth fixtures:

```python
def test_list_books_requires_auth(client: TestClient):
    resp = client.get("/api/books")
    assert resp.status_code == 401


def test_list_books_shows_only_own_books(client: TestClient, admin_user, regular_user, session, auth_headers_admin, auth_headers_user):
    from app.models import Book
    
    # Create book for admin
    admin_book = Book(title="Admin Book", user_id=admin_user.id)
    session.add(admin_book)
    
    # Create book for regular user
    user_book = Book(title="User Book", user_id=regular_user.id)
    session.add(user_book)
    session.commit()
    
    # Admin sees only their book
    resp = client.get("/api/books", headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Admin Book"
    
    # User sees only their book
    resp = client.get("/api/books", headers=auth_headers_user)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "User Book"


def test_create_book_sets_user_id(client: TestClient, admin_user, auth_headers_admin, session):
    resp = client.post("/api/books", json={"title": "New Book"}, headers=auth_headers_admin)
    assert resp.status_code == 201
    data = resp.json()
    
    from app.models import Book
    book = session.get(Book, data["id"])
    assert book.user_id == admin_user.id


def test_cannot_access_other_users_book(client: TestClient, admin_user, regular_user, session, auth_headers_user):
    from app.models import Book
    admin_book = Book(title="Admin Book", user_id=admin_user.id)
    session.add(admin_book)
    session.commit()
    
    # Regular user tries to get admin's book
    resp = client.get(f"/api/books/{admin_book.id}", headers=auth_headers_user)
    assert resp.status_code == 404  # Not found (hidden for security)
```

#### 7.1.4 User Management Tests

**File**: `backend/tests/test_users.py` (new)

```python
from fastapi.testclient import TestClient

def test_list_users_requires_admin(client: TestClient, auth_headers_user):
    resp = client.get("/api/users", headers=auth_headers_user)
    assert resp.status_code == 403


def test_list_users_admin(client: TestClient, admin_user, regular_user, auth_headers_admin):
    resp = client.get("/api/users", headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_create_user_admin(client: TestClient, auth_headers_admin):
    resp = client.post("/api/users", json={
        "email": "newuser@test.com",
        "firstname": "New",
        "lastname": "User",
        "password": "pass123",
        "role": "user",
    }, headers=auth_headers_admin)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@test.com"


def test_delete_user_admin(client: TestClient, regular_user, auth_headers_admin):
    resp = client.delete(f"/api/users/{regular_user.id}", headers=auth_headers_admin)
    assert resp.status_code == 204


def test_admin_cannot_delete_self(client: TestClient, admin_user, auth_headers_admin):
    resp = client.delete(f"/api/users/{admin_user.id}", headers=auth_headers_admin)
    assert resp.status_code == 403
```

#### 7.1.5 Profile Tests

**File**: `backend/tests/test_profile.py` (new)

```python
from fastapi.testclient import TestClient

def test_get_profile(client: TestClient, admin_user, auth_headers_admin):
    resp = client.get("/api/profile", headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@test.com"


def test_update_profile(client: TestClient, admin_user, auth_headers_admin):
    resp = client.patch("/api/profile", json={
        "firstname": "UpdatedFirstname",
    }, headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["firstname"] == "UpdatedFirstname"


def test_get_user_settings(client: TestClient, admin_user, auth_headers_admin):
    resp = client.get("/api/profile/settings", headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "en"


def test_update_user_settings(client: TestClient, admin_user, auth_headers_admin):
    resp = client.patch("/api/profile/settings", json={
        "language": "de",
    }, headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "de"
```

### 7.2 Frontend Tests (Optional, if E2E tests exist)

If using Playwright or similar:
- Test login flow
- Test setup flow
- Test profile edit
- Test logout
- Test route guards (unauthenticated redirect to /login)

### 7.3 Documentation Updates

**File**: `README.md` (update)

Add sections:
- **Authentication**: Describe user roles, setup process
- **Environment Variables**: Document `SECRET_KEY`, `COOKIE_SECURE`
- **First-Time Setup**: Explain `/setup` flow, default credentials (if migration creates default admin)
- **User Management**: Explain admin capabilities

**Example snippet**:
```markdown
## Authentication

LibrisLog uses cookie-based authentication with JWT tokens. On first run, you'll be redirected to the `/setup` page to create an admin account.

### User Roles
- **Admin**: Can create/delete users, manage all data
- **User**: Can manage their own books

### Environment Variables
- `SECRET_KEY`: Used for signing JWT tokens (required, change in production)
- `ACCESS_TOKEN_EXPIRE_HOURS`: Token expiration time (default: 24)
- `COOKIE_SECURE`: Set to `true` in production (requires HTTPS)

### First-Time Setup
1. Start the application
2. Navigate to `/setup`
3. Create an admin account
4. Login with your credentials
```

---

## Rollout Strategy

### Pre-Deployment Checklist
1. **Backup database**: Critical, as migration is destructive if data is lost
2. **Set `SECRET_KEY`** in production environment (generate securely, e.g., `openssl rand -hex 32`)
3. **Set `COOKIE_SECURE=true`** if using HTTPS (recommended)
4. **Test migration** on a copy of production data

### Deployment Steps
1. **Deploy backend**:
   - Update environment variables
   - Run `alembic upgrade head` (apply migration)
   - Verify migration: Check `users` table has default admin, `books` have `user_id`
   - Restart backend service

2. **Deploy frontend**:
   - Build and deploy updated frontend
   - Users will be redirected to `/setup` or `/login` on first visit

3. **Post-deployment**:
   - Test login flow
   - Verify book data isolation
   - Test user creation/deletion (if admin panel is built)

### Rollback Plan
If critical issues arise:
1. **Backend rollback**:
   - Redeploy previous backend version
   - Run `alembic downgrade -1` (rollback migration)
   - **Warning**: This will delete user accounts and remove `user_id` from books
   
2. **Frontend rollback**:
   - Redeploy previous frontend version

**Important**: Migration is not easily reversible if users have been created and books assigned. Test thoroughly before production deployment.

### User Communication
- **Breaking change**: All users must authenticate after upgrade
- **Existing data**: Books will be associated with the first admin account created
- **Setup**: First user to visit will be prompted to create an admin account
- **Password security**: Advise users to use strong passwords, especially for admin accounts

---

## Risks & Mitigations

### Risk 1: Migration Failure (Existing Books Orphaned)
**Impact**: High  
**Mitigation**:
- Migration script creates a default admin and assigns all books to that user
- Test migration on a copy of production database first
- Document rollback procedure

### Risk 2: Token Secret Leakage
**Impact**: Critical (allows token forgery)  
**Mitigation**:
- Use strong, randomly generated `SECRET_KEY` (32+ bytes)
- Store in environment variable, never commit to git
- Rotate secret if compromised (invalidates all tokens)

### Risk 3: Admin Self-Lockout
**Impact**: High  
**Mitigation**:
- Admins cannot delete themselves (enforced in backend)
- Ensure at least one admin exists (setup page gated)
- Document manual database recovery procedure (create admin via SQL if needed)

### Risk 4: CSRF Attacks (Cookie-based Auth)
**Impact**: Medium  
**Mitigation**:
- Use `SameSite=Lax` or `SameSite=Strict` on cookies (already in plan)
- Consider adding CSRF token for state-changing requests (future enhancement)

### Risk 5: Session Hijacking
**Impact**: Medium  
**Mitigation**:
- Use `httpOnly` and `secure` flags on cookies (already in plan)
- Set reasonable token expiration (24 hours default, configurable)
- Implement token refresh mechanism (future enhancement)

### Risk 6: Frontend Route Guard Bypass
**Impact**: Low (backend enforces auth)  
**Mitigation**:
- All backend endpoints require authentication (except `/auth/*`, `/covers/*`)
- Frontend guards are UX convenience, not security boundary

### Risk 7: Email Uniqueness Collisions (Case Sensitivity)
**Impact**: Low  
**Mitigation**:
- Use `COLLATE NOCASE` on email column (SQLite)
- Normalize email to lowercase before insertion (alternative)

### Risk 8: Password Strength
**Impact**: Medium  
**Mitigation**:
- Document password requirements in UI (e.g., min 8 characters)
- Consider adding password strength indicator (future enhancement)
- Use bcrypt with sufficient cost factor (default in passlib is secure)

### Risk 9: Broken Tests (All Book Tests Require Auth)
**Impact**: Medium (dev velocity)  
**Mitigation**:
- Update `conftest.py` with auth fixtures (already in plan)
- Update all existing tests to use auth headers
- Run full test suite before deployment

### Risk 10: Users Bypass Setup Page
**Impact**: Low  
**Mitigation**:
- Backend `/auth/setup` endpoint checks if admin exists (403 if exists)
- Frontend checks `setup-required` before allowing non-setup routes

---

## Implementation Order Summary

### Phase 1: Backend Auth Foundation (2-3 hours)
- Install dependencies
- Create User, UserSettings models
- Create auth schemas
- Implement password hashing and JWT utilities
- Update config

### Phase 2: Database Migration (1-2 hours)
- Create alembic migration
- Write upgrade/downgrade logic (including data migration)
- Apply migration and verify

### Phase 3: Backend Authorization (2-3 hours)
- Implement `get_current_user`, `require_admin` dependencies
- Update book endpoints for auth and data isolation
- Update import endpoints for auth

### Phase 4: Backend API Endpoints (3-4 hours)
- Implement `/auth/*` router (setup, login, logout, me)
- Implement `/users/*` router (admin CRUD)
- Implement `/profile/*` router (user self-management, settings)
- Register routers in main.py

### Phase 5: Frontend Authentication UI (4-5 hours)
- Create auth store
- Update API client with auth methods and 401 handling
- Create login page
- Create setup page
- Add route guards to layout

### Phase 6: Frontend User Profile & Settings Migration (3-4 hours)
- Create UserMenu component (avatar bubble dropdown)
- Add UserMenu to layout
- Create profile page
- Update i18n to load language from backend
- Add translation keys

### Phase 7: Testing & Documentation (4-5 hours)
- Update conftest.py with auth fixtures
- Write auth endpoint tests
- Update book tests for auth
- Write user management tests
- Write profile tests
- Update README

**Total Estimated Time**: 19-26 hours

---

## Appendix: Additional Considerations

### Future Enhancements
1. **Token Refresh**: Add refresh token flow for long-lived sessions
2. **2FA**: Two-factor authentication for admins
3. **Password Reset**: Email-based password reset flow
4. **Audit Log**: Track user actions (login, book creation, etc.)
5. **Rate Limiting**: Prevent brute-force login attempts
6. **User Avatars**: Upload custom avatars (instead of initials)
7. **User Roles Expansion**: Add custom roles (editor, viewer, etc.)
8. **OAuth**: Support Google/GitHub login

### Security Best Practices
- **HTTPS**: Always use HTTPS in production (`COOKIE_SECURE=true`)
- **Password Policy**: Enforce minimum length, complexity (consider `zxcvbn` for strength checking)
- **Secrets Management**: Use vault or secrets manager for `SECRET_KEY`
- **Dependency Updates**: Regularly update `passlib`, `python-jose`, FastAPI
- **Input Validation**: All user inputs are validated by Pydantic (already in place)

### Database Considerations
- **ON DELETE Behavior**: Current plan uses default (no CASCADE). Decide on policy:
  - Cascade: Deleting user deletes their books
  - Restrict: Prevent deletion if user has books (recommended)
  - Set Null: Books become unowned (problematic, `user_id` should be NOT NULL)
- **Indexes**: Ensure `user_id` on `books` is indexed (already in plan)
- **User Settings Defaults**: Migration creates default settings; consider lazy creation

### Frontend Considerations
- **Loading States**: Show spinners during auth checks (already in plan)
- **Error Handling**: Display user-friendly error messages (already in plan)
- **Session Expiration**: Handle 401 gracefully (redirect to login with message)
- **Back Button**: Ensure route guards work with browser navigation
- **SvelteKit SSR**: If using SSR, handle auth in `load` functions (not in plan, app is SPA)

---

## Conclusion

This plan provides a comprehensive roadmap to add multi-user authentication and authorization to LibrisLog. The implementation is broken into 7 phases, each with clear deliverables and test coverage. The rollout strategy includes migration safety checks and rollback procedures. Key risks are identified with mitigations.

**Next Steps**:
1. Review this plan with stakeholders
2. Set up a test environment for migration testing
3. Begin Phase 1 implementation
4. Proceed sequentially through phases, testing at each step

**Success Criteria**:
- Users can authenticate via email/password
- Data isolation: users see only their own books
- Admins can create/delete users
- Setup flow works for first-time users
- All existing tests pass (after auth updates)
- No security vulnerabilities in auth flow
