# Implementation Plan: Optional OIDC Authentication Support

## Overview

Add optional OpenID Connect (OIDC) authentication to allow users to link their accounts with external identity providers while maintaining the existing email+password login system as the primary authentication method.

**Key Principle**: OIDC is a secondary/convenience auth method, not a first-class authentication provider.

## Requirements Summary

1. **Optional Feature**: OIDC can be disabled; app works fully without it
2. **Dual Authentication**: Email+password login remains available even when OIDC is active
3. **Account Linking Required**: Users must manually link OIDC accounts to existing accounts
4. **No OIDC Registration**: Account creation still happens via admin UI/API only
5. **Clear User Guidance**: Unlinked users are informed to login via email+password first
6. **Environment-Based Config**: OIDC settings configured only via environment variables

## Architecture Overview

### Authentication Flow
```
┌─────────────────────────────────────────────────────────┐
│                      Login Page                          │
│  ┌──────────────────────┐  ┌────────────────────────┐  │
│  │ Email + Password     │  │ OIDC Provider Button   │  │
│  │ (Always available)   │  │ (If configured)        │  │
│  └──────────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                    │                      │
                    │                      ├──────┐
                    │                      │      │
                    ▼                      ▼      │
         ┌───────────────────┐   ┌─────────────┐│
         │ Existing Auth Flow│   │ OIDC Callback││
         │ (unchanged)       │   │ Handler      ││
         └───────────────────┘   └─────────────┘│
                    │                      │      │
                    │              ┌───────┘      │
                    │              │  NOT Linked? │
                    │              ▼              │
                    │     ┌────────────────────┐ │
                    │     │ Show Warning:      │ │
                    │     │ "Please login via  │ │
                    │     │ email+password and │ │
                    │     │ link account first"│ │
                    │     └────────────────────┘ │
                    │              │              │
                    │              │ IS Linked?   │
                    │              ▼              │
                    │     ┌────────────────────┐ │
                    │     │ Find User by       │ │
                    │     │ OIDC Provider ID   │ │
                    │     └────────────────────┘ │
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                                   ▼
                        ┌──────────────────┐
                        │ Authenticated    │
                        │ User Session     │
                        └──────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   Profile Page                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Link/Unlink OIDC Account                         │   │
│  │ • Show provider name from config                 │   │
│  │ • Show link status (linked/not linked)           │   │
│  │ • Button to link/unlink                          │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Phase 1: Backend - Database Schema

### 1.1 Create New Model for OIDC Linking

**File**: `backend/app/models.py`

Add a new table to store OIDC account linkings:

```python
class OidcLink(SQLModel, table=True):
    """Links a local user account to an OIDC provider account."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    # Provider info
    provider_name: str = Field(index=True)  # e.g., "keycloak", "auth0", etc.
    
    # OIDC subject identifier (unique per provider)
    oidc_sub: str = Field(index=True)  # The 'sub' claim from OIDC
    
    # Optional: store additional claims for display/debugging
    oidc_email: Optional[str] = None
    oidc_name: Optional[str] = None
    
    # Metadata
    linked_at: datetime = Field(default_factory=_utcnow)
    last_used_at: Optional[datetime] = None
    
    __table_args__ = (
        # Ensure a user can only link once per provider
        # and provider+sub is globally unique
        {"sqlite_unique": ["user_id", "provider_name"]},
        {"sqlite_unique": ["provider_name", "oidc_sub"]},
    )
```

### 1.2 Create Alembic Migration

**File**: `backend/alembic/versions/XXXX_add_oidc_link_table.py`

```bash
# Generate migration
cd backend
uv run alembic revision --autogenerate -m "add_oidc_link_table"
```

**Migration content** (auto-generated, but verify):
- Create `oidclink` table
- Add foreign key constraint to `user.id`
- Add unique constraints on `(user_id, provider_name)` and `(provider_name, oidc_sub)`
- Add indexes on `user_id`, `provider_name`, `oidc_sub`

## Phase 2: Backend - Configuration

### 2.1 Extend Settings

**File**: `backend/app/config.py`

```python
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./data/librislog.db"
    google_books_api_key: str = ""
    cors_origins: List[str] = ["http://localhost", "http://localhost:5173", "http://localhost:4173"]
    log_level: str = "INFO"
    covers_dir: str = "./data/covers"
    api_key_encryption_key: str = "CHANGE_ME_TO_32PLUS_CHARS"
    
    # OIDC Configuration (all optional)
    oidc_enabled: bool = False
    oidc_provider_name: str = ""  # Display name for UI button (e.g., "Company SSO")
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_well_known_url: str = ""  # e.g., https://provider.com/.well-known/openid-configuration
    
    def is_oidc_configured(self) -> bool:
        """Check if all required OIDC settings are present."""
        return (
            self.oidc_enabled
            and bool(self.oidc_provider_name)
            and bool(self.oidc_client_id)
            and bool(self.oidc_client_secret)
            and bool(self.oidc_well_known_url)
        )
```

### 2.2 Update `.env.example`

**File**: `.env.example`

```bash
# Backend settings
DATABASE_URL=sqlite:///./data/librislog.db
GOOGLE_BOOKS_API_KEY=        # REQUIRED for Google Books fallback
CORS_ORIGINS=["http://localhost:8080"]
LOG_LEVEL=INFO
COVERS_DIR=./data/covers

# OIDC Authentication (Optional)
OIDC_ENABLED=false                    # Set to true to enable OIDC login
OIDC_PROVIDER_NAME=Company SSO        # Display name shown on login button
OIDC_CLIENT_ID=                       # Client ID from your OIDC provider
OIDC_CLIENT_SECRET=                   # Client secret from your OIDC provider
OIDC_WELL_KNOWN_URL=                  # OpenID configuration URL
                                      # Example: https://accounts.google.com/.well-known/openid-configuration
                                      # Example: https://keycloak.example.com/realms/myrealm/.well-known/openid-configuration

# Frontend settings (build-time)
PUBLIC_DEFAULT_LOCALE=en
```

## Phase 3: Backend - OIDC Integration

### 3.1 Install Dependencies

**File**: `backend/pyproject.toml`

Add to dependencies:
```toml
dependencies = [
    # ... existing dependencies
    "authlib>=1.3.0",
]
```

Run:
```bash
cd backend
uv sync
```

### 3.2 Initialize OAuth Client

**File**: `backend/app/oidc.py` (new file)

```python
"""OIDC authentication integration."""
from typing import Optional
from authlib.integrations.starlette_client import OAuth
from fastapi import Request

from app.config import settings


_oauth_instance: Optional[OAuth] = None


def get_oauth() -> Optional[OAuth]:
    """
    Get or create the OAuth instance.
    Returns None if OIDC is not configured.
    """
    global _oauth_instance
    
    if not settings.is_oidc_configured():
        return None
    
    if _oauth_instance is None:
        _oauth_instance = OAuth()
        _oauth_instance.register(
            name="oidc",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            server_metadata_url=settings.oidc_well_known_url,
            client_kwargs={
                "scope": "openid email profile",
            },
        )
    
    return _oauth_instance


def is_oidc_enabled() -> bool:
    """Check if OIDC is enabled and properly configured."""
    return settings.is_oidc_configured()


def get_oidc_provider_display_name() -> str:
    """Get the display name for the OIDC provider."""
    return settings.oidc_provider_name
```

### 3.3 Add Schemas for OIDC

**File**: `backend/app/schemas.py`

Add new schemas:

```python
class OidcConfigResponse(SQLModel):
    """Public OIDC configuration (for frontend)."""
    enabled: bool
    provider_name: str  # Empty if not enabled


class OidcLinkStatusResponse(SQLModel):
    """OIDC link status for current user."""
    linked: bool
    provider_name: str
    linked_at: Optional[datetime] = None
    oidc_email: Optional[str] = None
    oidc_name: Optional[str] = None


class OidcLoginErrorResponse(SQLModel):
    """Error response for OIDC login attempts."""
    error: str
    error_description: str
    needs_link: bool = False  # True if user exists but hasn't linked account
```

### 3.4 Create OIDC Router

**File**: `backend/app/routers/oidc.py` (new file)

```python
"""OIDC authentication routes."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user_by_api_key, decrypt_api_key
from app.config import settings
from app.database import get_session
from app.models import OidcLink, User, ApiKey
from app.oidc import get_oauth, is_oidc_enabled, get_oidc_provider_display_name
from app.schemas import OidcConfigResponse, OidcLinkStatusResponse, UserRead


router = APIRouter(prefix="/api/oidc", tags=["oidc"])


@router.get("/config", response_model=OidcConfigResponse)
def get_oidc_config() -> OidcConfigResponse:
    """
    Get OIDC configuration (public endpoint).
    Used by frontend to show/hide OIDC login button.
    """
    return OidcConfigResponse(
        enabled=is_oidc_enabled(),
        provider_name=get_oidc_provider_display_name() if is_oidc_enabled() else "",
    )


@router.get("/login")
async def oidc_login(request: Request) -> RedirectResponse:
    """
    Initiate OIDC login flow.
    Redirects user to OIDC provider's authorization endpoint.
    """
    oauth = get_oauth()
    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC is not configured",
        )
    
    # Build callback URL
    callback_url = str(request.url_for("oidc_callback"))
    
    # Redirect to OIDC provider
    return await oauth.oidc.authorize_redirect(request, callback_url)


@router.get("/callback")
async def oidc_callback(
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """
    Handle OIDC callback after user authenticates with provider.
    
    Returns:
        - Success: {"user": UserRead, "api_key": str}
        - Error: {"error": str, "error_description": str, "needs_link": bool}
    """
    oauth = get_oauth()
    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC is not configured",
        )
    
    try:
        # Exchange authorization code for token
        token = await oauth.oidc.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to authorize with OIDC provider: {str(e)}",
        )
    
    # Extract user info from token
    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No user info received from OIDC provider",
        )
    
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No 'sub' claim in OIDC token",
        )
    
    provider_name = settings.oidc_provider_name
    
    # Check if this OIDC account is linked to a user
    link = session.exec(
        select(OidcLink)
        .where(OidcLink.provider_name == provider_name, OidcLink.oidc_sub == oidc_sub)
    ).first()
    
    if not link:
        # Not linked - return error with needs_link flag
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_not_linked",
                "error_description": (
                    f"Your {provider_name} account is not linked to any Librislog account. "
                    "Please log in with email and password, then link your account in your profile."
                ),
                "needs_link": True,
            },
        )
    
    # Get the linked user
    user = session.get(User, link.user_id)
    if not user:
        # This shouldn't happen, but handle gracefully
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Linked user account not found",
        )
    
    # Update last_used_at for the link
    link.last_used_at = datetime.now(timezone.utc)
    session.add(link)
    
    # Get user's primary API key
    primary_key = session.exec(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.is_primary.is_(True),
            ApiKey.revoked_at.is_(None),
        )
    ).first()
    
    if not primary_key or not primary_key.key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Primary API key missing",
        )
    
    # Update API key last_used_at
    primary_key.last_used_at = datetime.now(timezone.utc)
    session.add(primary_key)
    session.commit()
    
    # Return user and API key (same format as /api/auth/login)
    return {
        "user": UserRead.model_validate(user),
        "api_key": decrypt_api_key(primary_key.key_encrypted),
    }


@router.get("/link-status", response_model=OidcLinkStatusResponse)
def get_link_status(
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> OidcLinkStatusResponse:
    """
    Check if current user has linked their OIDC account.
    Requires authentication.
    """
    if not is_oidc_enabled():
        return OidcLinkStatusResponse(
            linked=False,
            provider_name="",
        )
    
    provider_name = get_oidc_provider_display_name()
    
    link = session.exec(
        select(OidcLink)
        .where(
            OidcLink.user_id == current_user.id,
            OidcLink.provider_name == provider_name,
        )
    ).first()
    
    if link:
        return OidcLinkStatusResponse(
            linked=True,
            provider_name=provider_name,
            linked_at=link.linked_at,
            oidc_email=link.oidc_email,
            oidc_name=link.oidc_name,
        )
    
    return OidcLinkStatusResponse(
        linked=False,
        provider_name=provider_name,
    )


@router.post("/link")
async def link_oidc_account(
    request: Request,
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """
    Initiate OIDC account linking for the current user.
    Redirects to OIDC provider, then to /api/oidc/link-callback.
    """
    oauth = get_oauth()
    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC is not configured",
        )
    
    # Store user_id in session for callback
    # Note: This requires session middleware
    request.session["oidc_link_user_id"] = current_user.id
    
    callback_url = str(request.url_for("oidc_link_callback"))
    return await oauth.oidc.authorize_redirect(request, callback_url)


@router.get("/link-callback")
async def oidc_link_callback(
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """
    Handle OIDC callback for account linking.
    Links the OIDC account to the authenticated user.
    """
    oauth = get_oauth()
    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC is not configured",
        )
    
    # Get user_id from session
    user_id = request.session.get("oidc_link_user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user session found. Please try again.",
        )
    
    try:
        token = await oauth.oidc.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to authorize with OIDC provider: {str(e)}",
        )
    
    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No user info received from OIDC provider",
        )
    
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No 'sub' claim in OIDC token",
        )
    
    provider_name = settings.oidc_provider_name
    
    # Check if this OIDC account is already linked to another user
    existing_link = session.exec(
        select(OidcLink)
        .where(OidcLink.provider_name == provider_name, OidcLink.oidc_sub == oidc_sub)
    ).first()
    
    if existing_link and existing_link.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This {provider_name} account is already linked to another user",
        )
    
    # Check if this user already has a link for this provider
    user_existing_link = session.exec(
        select(OidcLink)
        .where(OidcLink.user_id == user_id, OidcLink.provider_name == provider_name)
    ).first()
    
    if user_existing_link:
        # Update existing link
        user_existing_link.oidc_sub = oidc_sub
        user_existing_link.oidc_email = userinfo.get("email")
        user_existing_link.oidc_name = userinfo.get("name")
        user_existing_link.linked_at = datetime.now(timezone.utc)
        session.add(user_existing_link)
    else:
        # Create new link
        link = OidcLink(
            user_id=user_id,
            provider_name=provider_name,
            oidc_sub=oidc_sub,
            oidc_email=userinfo.get("email"),
            oidc_name=userinfo.get("name"),
        )
        session.add(link)
    
    session.commit()
    
    # Clear session
    request.session.pop("oidc_link_user_id", None)
    
    return {"message": f"Successfully linked {provider_name} account"}


@router.delete("/unlink")
def unlink_oidc_account(
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> dict:
    """
    Unlink the current user's OIDC account.
    """
    if not is_oidc_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC is not enabled",
        )
    
    provider_name = get_oidc_provider_display_name()
    
    link = session.exec(
        select(OidcLink)
        .where(
            OidcLink.user_id == current_user.id,
            OidcLink.provider_name == provider_name,
        )
    ).first()
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No linked OIDC account found",
        )
    
    session.delete(link)
    session.commit()
    
    return {"message": f"Successfully unlinked {provider_name} account"}
```

### 3.5 Register OIDC Router

**File**: `backend/app/main.py`

Add OIDC router import and registration:

```python
from app.routers import auth, books, users, oidc

# Register routers
app.include_router(auth.router)
app.include_router(books.router)
app.include_router(users.router)
app.include_router(oidc.router)  # Add this
```

### 3.6 Add Session Middleware

OIDC linking flow requires session storage for the linking callback.

**File**: `backend/app/main.py`

```python
from starlette.middleware.sessions import SessionMiddleware

# Add session middleware (after CORS)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.api_key_encryption_key,  # Reuse existing secret
    max_age=3600,  # 1 hour
    same_site="lax",
)
```

## Phase 4: Frontend - UI Changes

### 4.1 Add OIDC Config Types

**File**: `frontend/src/lib/types.ts`

```typescript
export interface OidcConfig {
	enabled: boolean;
	provider_name: string;
}

export interface OidcLinkStatus {
	linked: boolean;
	provider_name: string;
	linked_at?: string;
	oidc_email?: string;
	oidc_name?: string;
}
```

### 4.2 Extend API Client

**File**: `frontend/src/lib/api.ts`

Add OIDC API methods:

```typescript
export const api = {
	// ... existing methods
	
	oidc: {
		async getConfig(): Promise<OidcConfig> {
			const res = await fetch(`${API_BASE}/api/oidc/config`);
			if (!res.ok) throw new Error('Failed to fetch OIDC config');
			return res.json();
		},
		
		async getLinkStatus(apiKey: string): Promise<OidcLinkStatus> {
			const res = await fetch(`${API_BASE}/api/oidc/link-status`, {
				headers: { 'X-API-Key': apiKey }
			});
			if (!res.ok) throw new Error('Failed to fetch OIDC link status');
			return res.json();
		},
		
		getLoginUrl(): string {
			return `${API_BASE}/api/oidc/login`;
		},
		
		getLinkUrl(): string {
			return `${API_BASE}/api/oidc/link`;
		},
		
		async unlink(apiKey: string): Promise<void> {
			const res = await fetch(`${API_BASE}/api/oidc/unlink`, {
				method: 'DELETE',
				headers: { 'X-API-Key': apiKey }
			});
			if (!res.ok) throw new Error('Failed to unlink OIDC account');
		}
	}
};
```

### 4.3 Update Login Page

**File**: `frontend/src/routes/login/+page.svelte`

Add OIDC login button below the password login form:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { currentUser, setAuthKey } from '$lib/stores/auth';
	import { _, locale, setLocale, SUPPORTED_LOCALES, type AppLocale } from '$lib/i18n';
	import type { OidcConfig } from '$lib/types';

	let email = $state('');
	let password = $state('');
	let selectedLanguage = $state<AppLocale>('en');
	let loading = $state(false);
	let error = $state('');
	let oidcConfig = $state<OidcConfig | null>(null);

	$effect(() => {
		if (SUPPORTED_LOCALES.includes($locale as AppLocale)) {
			selectedLanguage = $locale as AppLocale;
		}
	});

	onMount(async () => {
		// Fetch OIDC config
		try {
			oidcConfig = await api.oidc.getConfig();
		} catch (e) {
			console.error('Failed to load OIDC config:', e);
		}
	});

	function onLanguageChange(event: Event) {
		const next = (event.currentTarget as HTMLSelectElement).value as AppLocale;
		if (!SUPPORTED_LOCALES.includes(next)) return;
		selectedLanguage = next;
		setLocale(next);
	}

	async function submit() {
		error = '';
		loading = true;
		try {
			const result = await api.auth.login({ email, password });
			setAuthKey(result.api_key);
			currentUser.set(result.user);
			await api.profile.updateSettings({ language: selectedLanguage });
			setLocale(selectedLanguage);
			await goto('/');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $_('auth.loginFailed');
		} finally {
			loading = false;
		}
	}
	
	function loginWithOidc() {
		// Redirect to backend OIDC login endpoint
		window.location.href = api.oidc.getLoginUrl();
	}
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			<h1 class="text-2xl font-bold">{$_('auth.login')}</h1>
			<label class="form-control max-w-xs">
				<span class="label label-text">{$_('settings.languageTitle')}</span>
				<select class="select select-bordered" value={selectedLanguage} onchange={onLanguageChange}>
					{#each SUPPORTED_LOCALES as code}
						<option value={code}>{$_(`languages.${code}`)}</option>
					{/each}
				</select>
			</label>
			{#if error}
				<div class="alert alert-error text-sm"><span>{error}</span></div>
			{/if}
			<form class="flex flex-col gap-3" onsubmit={(e) => { e.preventDefault(); submit(); }}>
				<label class="form-control">
					<span class="label label-text">{$_('auth.email')}</span>
					<input type="email" class="input input-bordered" bind:value={email} required disabled={loading} />
				</label>
				<label class="form-control">
					<span class="label label-text">{$_('auth.password')}</span>
					<input type="password" class="input input-bordered" bind:value={password} required disabled={loading} />
				</label>
				<button type="submit" class="btn btn-primary" disabled={loading}>
					{loading ? $_('common.loadingEllipsis') : $_('auth.login')}
				</button>
			</form>
			
			{#if oidcConfig?.enabled}
				<div class="divider text-xs text-base-content/50">OR</div>
				<button 
					type="button" 
					class="btn btn-outline" 
					onclick={loginWithOidc}
					disabled={loading}
				>
					{$_('auth.loginWith')} {oidcConfig.provider_name}
				</button>
			{/if}
		</div>
	</div>
</div>
```

### 4.4 Add OIDC Callback Handler

**File**: `frontend/src/routes/auth/oidc/callback/+page.svelte` (new file)

Handle the OIDC callback and redirect:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { currentUser, setAuthKey } from '$lib/stores/auth';
	import { _ } from '$lib/i18n';

	let error = $state('');
	let needsLink = $state(false);

	onMount(async () => {
		// The backend handles the token exchange via cookies/session
		// Just check if we got the callback parameters
		const url = new URL(window.location.href);
		const code = url.searchParams.get('code');
		const errorParam = url.searchParams.get('error');

		if (errorParam) {
			error = errorParam;
			return;
		}

		if (!code) {
			error = 'No authorization code received';
			return;
		}

		// Backend callback handler should have set user session
		// Now fetch to get user info and API key
		try {
			const res = await fetch(`/api/oidc/callback${window.location.search}`);
			if (!res.ok) {
				const data = await res.json();
				if (data.needs_link) {
					needsLink = true;
					error = data.error_description || 'Account not linked';
				} else {
					error = data.detail || 'Authentication failed';
				}
				return;
			}

			const result = await res.json();
			setAuthKey(result.api_key);
			currentUser.set(result.user);
			await goto('/');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Authentication failed';
		}
	});
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			{#if error}
				<h2 class="text-xl font-bold text-error">{$_('auth.loginFailed')}</h2>
				<div class="alert alert-error text-sm">
					<span>{error}</span>
				</div>
				{#if needsLink}
					<div class="alert alert-info text-sm">
						<span>
							{$_('oidc.needsLinkInstruction')}
						</span>
					</div>
					<button class="btn btn-primary" onclick={() => goto('/login')}>
						{$_('auth.loginWithPassword')}
					</button>
				{:else}
					<button class="btn btn-ghost" onclick={() => goto('/login')}>
						{$_('common.backToLogin')}
					</button>
				{/if}
			{:else}
				<h2 class="text-xl font-bold">{$_('auth.authenticating')}</h2>
				<p class="text-sm text-base-content/70">{$_('common.pleaseWait')}</p>
				<span class="loading loading-spinner loading-lg mx-auto"></span>
			{/if}
		</div>
	</div>
</div>
```

### 4.5 Update Profile Page - Add OIDC Linking Section

**File**: `frontend/src/routes/profile/+page.svelte`

Add OIDC account linking section after the API keys section:

```svelte
<script lang="ts">
	// ... existing imports
	import type { OidcConfig, OidcLinkStatus } from '$lib/types';

	// ... existing state
	let oidcConfig = $state<OidcConfig | null>(null);
	let oidcLinkStatus = $state<OidcLinkStatus | null>(null);
	let oidcLoading = $state(false);

	async function load() {
		const settings = await api.profile.getSettings();
		language = settings.language;
		keys = await api.profile.listApiKeys();
		
		// Load OIDC status
		try {
			oidcConfig = await api.oidc.getConfig();
			if (oidcConfig.enabled && $apiKey) {
				oidcLinkStatus = await api.oidc.getLinkStatus($apiKey);
			}
		} catch (e) {
			console.error('Failed to load OIDC status:', e);
		}
	}

	void load();

	function linkOidcAccount() {
		// Redirect to OIDC linking flow
		window.location.href = api.oidc.getLinkUrl();
	}

	async function unlinkOidcAccount() {
		if (!$apiKey) return;
		oidcLoading = true;
		try {
			await api.oidc.unlink($apiKey);
			// Reload status
			if (oidcConfig?.enabled) {
				oidcLinkStatus = await api.oidc.getLinkStatus($apiKey);
			}
		} catch (e) {
			console.error('Failed to unlink OIDC account:', e);
		} finally {
			oidcLoading = false;
		}
	}

	// ... rest of existing code
</script>

<div class="max-w-3xl mx-auto flex flex-col gap-6">
	<h1 class="text-2xl font-bold">{$_('user.profile')}</h1>

	<!-- Existing profile card -->
	<!-- ... -->

	<!-- Existing language card -->
	<!-- ... -->

	<!-- Existing API keys card -->
	<!-- ... -->

	<!-- OIDC Account Linking Card -->
	{#if oidcConfig?.enabled}
		<div class="card bg-base-100 border border-base-200 shadow-sm">
			<div class="card-body gap-3">
				<h2 class="text-lg font-semibold">{$_('oidc.linkAccount')}</h2>
				<p class="text-sm text-base-content/70">
					{$_('oidc.linkDescription', { provider: oidcConfig.provider_name })}
				</p>
				
				{#if oidcLinkStatus?.linked}
					<div class="alert alert-success text-sm">
						<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
							<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
						</svg>
						<div class="flex flex-col">
							<span class="font-semibold">{$_('oidc.accountLinked')}</span>
							{#if oidcLinkStatus.oidc_email || oidcLinkStatus.oidc_name}
								<span class="text-xs opacity-80">
									{oidcLinkStatus.oidc_name || ''} 
									{oidcLinkStatus.oidc_email ? `(${oidcLinkStatus.oidc_email})` : ''}
								</span>
							{/if}
						</div>
					</div>
					<button 
						class="btn btn-error btn-outline btn-sm self-start" 
						onclick={unlinkOidcAccount}
						disabled={oidcLoading}
					>
						{oidcLoading ? $_('common.loadingEllipsis') : $_('oidc.unlinkAccount')}
					</button>
				{:else}
					<div class="alert alert-info text-sm">
						<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
							<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
						</svg>
						<span>{$_('oidc.notLinked')}</span>
					</div>
					<button 
						class="btn btn-primary btn-sm self-start" 
						onclick={linkOidcAccount}
					>
						{$_('oidc.linkNow', { provider: oidcConfig.provider_name })}
					</button>
				{/if}
			</div>
		</div>
	{/if}
</div>

<!-- Existing API key delete modal -->
<!-- ... -->
```

### 4.6 Add OIDC Link Callback Handler

**File**: `frontend/src/routes/auth/oidc/link-callback/+page.svelte` (new file)

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { _ } from '$lib/i18n';

	let success = $state(false);
	let error = $state('');

	onMount(async () => {
		const url = new URL(window.location.href);
		const code = url.searchParams.get('code');
		const errorParam = url.searchParams.get('error');

		if (errorParam) {
			error = errorParam;
			return;
		}

		if (!code) {
			error = 'No authorization code received';
			return;
		}

		try {
			const res = await fetch(`/api/oidc/link-callback${window.location.search}`);
			if (!res.ok) {
				const data = await res.json();
				error = data.detail || 'Link failed';
				return;
			}

			success = true;
			setTimeout(() => goto('/profile'), 2000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Link failed';
		}
	});
</script>

<div class="min-h-screen bg-base-200 grid place-items-center p-4">
	<div class="card bg-base-100 border border-base-200 shadow-sm w-full max-w-md">
		<div class="card-body gap-4">
			{#if success}
				<h2 class="text-xl font-bold text-success">{$_('oidc.linkSuccess')}</h2>
				<p class="text-sm text-base-content/70">{$_('oidc.redirectingToProfile')}</p>
			{:else if error}
				<h2 class="text-xl font-bold text-error">{$_('oidc.linkFailed')}</h2>
				<div class="alert alert-error text-sm">
					<span>{error}</span>
				</div>
				<button class="btn btn-ghost" onclick={() => goto('/profile')}>
					{$_('common.backToProfile')}
				</button>
			{:else}
				<h2 class="text-xl font-bold">{$_('oidc.linking')}</h2>
				<p class="text-sm text-base-content/70">{$_('common.pleaseWait')}</p>
				<span class="loading loading-spinner loading-lg mx-auto"></span>
			{/if}
		</div>
	</div>
</div>
```

### 4.7 Add i18n Translations

**File**: `frontend/src/lib/i18n/en.json`

```json
{
	"auth": {
		// ... existing
		"loginWith": "Login with",
		"loginWithPassword": "Login with email & password",
		"authenticating": "Authenticating..."
	},
	"oidc": {
		"linkAccount": "Link External Account",
		"linkDescription": "Link your {provider} account to enable quick login",
		"accountLinked": "Account linked successfully",
		"notLinked": "Your account is not linked",
		"linkNow": "Link {provider} account",
		"unlinkAccount": "Unlink account",
		"linkSuccess": "Account linked successfully!",
		"linkFailed": "Failed to link account",
		"linking": "Linking account...",
		"redirectingToProfile": "Redirecting to profile...",
		"needsLinkInstruction": "To use this login method, first log in with your email and password, then link your external account in your profile."
	},
	"common": {
		// ... existing
		"backToLogin": "Back to login",
		"backToProfile": "Back to profile",
		"pleaseWait": "Please wait..."
	}
}
```

**File**: `frontend/src/lib/i18n/de.json`

```json
{
	"auth": {
		// ... existing
		"loginWith": "Anmelden mit",
		"loginWithPassword": "Mit E-Mail & Passwort anmelden",
		"authenticating": "Authentifiziere..."
	},
	"oidc": {
		"linkAccount": "Externes Konto verknüpfen",
		"linkDescription": "Verknüpfen Sie Ihr {provider}-Konto für schnelle Anmeldung",
		"accountLinked": "Konto erfolgreich verknüpft",
		"notLinked": "Ihr Konto ist nicht verknüpft",
		"linkNow": "{provider}-Konto verknüpfen",
		"unlinkAccount": "Verknüpfung aufheben",
		"linkSuccess": "Konto erfolgreich verknüpft!",
		"linkFailed": "Verknüpfung fehlgeschlagen",
		"linking": "Verknüpfe Konto...",
		"redirectingToProfile": "Weiterleitung zum Profil...",
		"needsLinkInstruction": "Um diese Anmeldemethode zu nutzen, melden Sie sich zuerst mit E-Mail und Passwort an und verknüpfen Sie dann Ihr externes Konto in Ihrem Profil."
	},
	"common": {
		// ... existing
		"backToLogin": "Zurück zur Anmeldung",
		"backToProfile": "Zurück zum Profil",
		"pleaseWait": "Bitte warten..."
	}
}
```

## Phase 5: Testing

### 5.1 Backend Tests

**File**: `backend/tests/test_oidc.py` (new file)

```python
"""Tests for OIDC authentication."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import User, OidcLink, UserRole
from app.main import app


@pytest.fixture
def mock_oauth():
    """Mock OAuth instance for testing."""
    with patch("app.routers.oidc.get_oauth") as mock:
        oauth_mock = MagicMock()
        oauth_mock.oidc = MagicMock()
        mock.return_value = oauth_mock
        yield oauth_mock


@pytest.fixture
def mock_oidc_enabled():
    """Mock OIDC as enabled."""
    with patch("app.routers.oidc.is_oidc_enabled", return_value=True):
        with patch("app.routers.oidc.get_oidc_provider_display_name", return_value="TestProvider"):
            yield


def test_oidc_config_disabled(client: TestClient):
    """Test OIDC config endpoint when OIDC is disabled."""
    with patch("app.routers.oidc.is_oidc_enabled", return_value=False):
        response = client.get("/api/oidc/config")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["provider_name"] == ""


def test_oidc_config_enabled(client: TestClient):
    """Test OIDC config endpoint when OIDC is enabled."""
    with patch("app.routers.oidc.is_oidc_enabled", return_value=True):
        with patch("app.routers.oidc.get_oidc_provider_display_name", return_value="TestProvider"):
            response = client.get("/api/oidc/config")
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
            assert data["provider_name"] == "TestProvider"


def test_oidc_login_not_configured(client: TestClient):
    """Test OIDC login when not configured."""
    with patch("app.routers.oidc.get_oauth", return_value=None):
        response = client.get("/api/oidc/login", follow_redirects=False)
        assert response.status_code == 503


def test_oidc_callback_not_linked(
    client: TestClient,
    session: Session,
    test_user: User,
    mock_oauth: MagicMock,
    mock_oidc_enabled,
):
    """Test OIDC callback when user hasn't linked account."""
    # Mock token exchange
    mock_oauth.oidc.authorize_access_token = AsyncMock(return_value={
        "userinfo": {
            "sub": "oidc-subject-123",
            "email": "test@example.com",
            "name": "Test User"
        }
    })
    
    response = client.get("/api/oidc/callback?code=test_code")
    assert response.status_code == 403
    data = response.json()
    assert "account_not_linked" in data["detail"]["error"]
    assert data["detail"]["needs_link"] is True


def test_oidc_callback_linked(
    client: TestClient,
    session: Session,
    test_user: User,
    mock_oauth: MagicMock,
    mock_oidc_enabled,
):
    """Test OIDC callback when user has linked account."""
    # Create OIDC link
    link = OidcLink(
        user_id=test_user.id,
        provider_name="TestProvider",
        oidc_sub="oidc-subject-123",
        oidc_email="test@example.com",
    )
    session.add(link)
    session.commit()
    
    # Mock token exchange
    mock_oauth.oidc.authorize_access_token = AsyncMock(return_value={
        "userinfo": {
            "sub": "oidc-subject-123",
            "email": "test@example.com",
            "name": "Test User"
        }
    })
    
    response = client.get("/api/oidc/callback?code=test_code")
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "api_key" in data
    assert data["user"]["email"] == test_user.email


def test_get_link_status_not_linked(
    client: TestClient,
    test_user: User,
    auth_headers: dict,
    mock_oidc_enabled,
):
    """Test getting link status when not linked."""
    response = client.get("/api/oidc/link-status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is False
    assert data["provider_name"] == "TestProvider"


def test_get_link_status_linked(
    client: TestClient,
    session: Session,
    test_user: User,
    auth_headers: dict,
    mock_oidc_enabled,
):
    """Test getting link status when linked."""
    link = OidcLink(
        user_id=test_user.id,
        provider_name="TestProvider",
        oidc_sub="oidc-subject-123",
        oidc_email="test@example.com",
        oidc_name="Test User",
    )
    session.add(link)
    session.commit()
    
    response = client.get("/api/oidc/link-status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is True
    assert data["provider_name"] == "TestProvider"
    assert data["oidc_email"] == "test@example.com"


def test_unlink_oidc_account(
    client: TestClient,
    session: Session,
    test_user: User,
    auth_headers: dict,
    mock_oidc_enabled,
):
    """Test unlinking OIDC account."""
    link = OidcLink(
        user_id=test_user.id,
        provider_name="TestProvider",
        oidc_sub="oidc-subject-123",
    )
    session.add(link)
    session.commit()
    
    response = client.delete("/api/oidc/unlink", headers=auth_headers)
    assert response.status_code == 200
    
    # Verify link is deleted
    from sqlmodel import select
    remaining_link = session.exec(
        select(OidcLink).where(OidcLink.user_id == test_user.id)
    ).first()
    assert remaining_link is None
```

### 5.2 Integration Test Scenarios

Create manual integration test scenarios:

**File**: `.plan/22-optional-oidc-auth-test-scenarios.md`

```markdown
# OIDC Integration Test Scenarios

## Setup
1. Configure a test OIDC provider (e.g., Keycloak locally)
2. Set environment variables in `.env`:
   ```
   OIDC_ENABLED=true
   OIDC_PROVIDER_NAME=Test SSO
   OIDC_CLIENT_ID=<client-id>
   OIDC_CLIENT_SECRET=<client-secret>
   OIDC_WELL_KNOWN_URL=<well-known-url>
   ```

## Test Cases

### TC1: OIDC Login Button Visibility
**Steps:**
1. Navigate to login page
2. Verify "Login with Test SSO" button is visible
3. Disable OIDC (set OIDC_ENABLED=false)
4. Refresh page
5. Verify button is NOT visible

**Expected:** Button only visible when OIDC is enabled

### TC2: OIDC Login - Unlinked Account
**Steps:**
1. Create a user via admin UI (email: user@example.com)
2. Click "Login with Test SSO" button
3. Authenticate with OIDC provider
4. Verify error message: "Your Test SSO account is not linked..."
5. Verify suggestion to login with email+password

**Expected:** Login fails with helpful error message

### TC3: Account Linking Flow
**Steps:**
1. Login with email+password
2. Navigate to profile page
3. Verify "Link External Account" section is visible
4. Click "Link Test SSO account" button
5. Authenticate with OIDC provider
6. Verify success message
7. Verify account shows as linked with OIDC email/name

**Expected:** Account successfully linked

### TC4: OIDC Login - Linked Account
**Steps:**
1. Logout
2. Click "Login with Test SSO" button
3. Authenticate with OIDC provider
4. Verify successful login
5. Verify redirected to dashboard

**Expected:** Login succeeds without password

### TC5: Account Unlinking
**Steps:**
1. Login with email+password
2. Navigate to profile page
3. Click "Unlink account" button
4. Verify account shows as not linked
5. Logout
6. Attempt OIDC login
7. Verify error message (account not linked)

**Expected:** Unlinking removes OIDC login capability

### TC6: Duplicate OIDC Account
**Steps:**
1. Link user A's account to OIDC account X
2. Login as user B (email+password)
3. Attempt to link user B to OIDC account X
4. Verify error: "This Test SSO account is already linked to another user"

**Expected:** Prevents one OIDC account from being linked to multiple users

### TC7: Email+Password Always Works
**Steps:**
1. Link account with OIDC
2. Logout
3. Login with email+password
4. Verify successful login

**Expected:** Email+password login remains functional even with OIDC linked

### TC8: Multiple Providers (Future)
**Note:** Current implementation supports only one provider at a time.
**Future:** If supporting multiple providers, test linking multiple OIDC accounts.
```

## Phase 6: Documentation

### 6.1 Update README

**File**: `README.md`

Add OIDC section to configuration documentation:

```markdown
## Optional OIDC Authentication

Librislog supports optional OpenID Connect (OIDC) authentication for enterprise SSO integration.

### Important Notes

- **OIDC is optional**: The app works fully without it.
- **Email+password is primary**: Even with OIDC enabled, users can always login with email and password.
- **No OIDC registration**: Users must be created via the admin UI. OIDC only provides login convenience.
- **Manual linking required**: Users must link their OIDC account to their existing account via the profile page.

### Configuration

Add these environment variables to enable OIDC:

```bash
OIDC_ENABLED=true
OIDC_PROVIDER_NAME="Company SSO"
OIDC_CLIENT_ID="your-client-id"
OIDC_CLIENT_SECRET="your-client-secret"
OIDC_WELL_KNOWN_URL="https://provider.com/.well-known/openid-configuration"
```

### User Workflow

1. Admin creates user account via admin UI
2. User logs in with email + password
3. User navigates to profile page
4. User clicks "Link [Provider] account"
5. User authenticates with OIDC provider
6. Account is linked
7. User can now login via OIDC or email+password

### Supported Providers

Any OpenID Connect 1.0 compliant provider, including:
- Keycloak
- Auth0
- Okta
- Azure AD / Microsoft Entra ID
- Google Workspace
- Custom OIDC providers

### Security Considerations

- OIDC accounts are linked to users via the `sub` claim
- Session secrets use the existing `API_KEY_ENCRYPTION_KEY`
- OIDC tokens are validated by the Authlib library
- Account linking requires an active authenticated session
```

### 6.2 Create OIDC Setup Guide

**File**: `docs/oidc-setup-guide.md` (new file)

```markdown
# OIDC Setup Guide

This guide walks through setting up OIDC authentication with various providers.

## General Setup Steps

1. **Register Application with OIDC Provider**
   - Create a new OAuth 2.0 / OIDC application
   - Note the Client ID and Client Secret
   - Configure redirect URI: `https://your-domain.com/api/oidc/callback`
   - Add linking redirect URI: `https://your-domain.com/api/oidc/link-callback`
   - Request scopes: `openid`, `email`, `profile`

2. **Configure Librislog**
   - Add environment variables to `.env`
   - Restart backend service

3. **Test Configuration**
   - Navigate to login page
   - Verify OIDC button appears
   - Test the full linking flow

## Provider-Specific Guides

### Keycloak

1. **Create a Realm** (or use existing)
2. **Create Client:**
   - Client ID: `librislog`
   - Client Protocol: `openid-connect`
   - Access Type: `confidential`
   - Valid Redirect URIs:
     - `https://your-domain.com/api/oidc/callback`
     - `https://your-domain.com/api/oidc/link-callback`
3. **Get Credentials:**
   - Navigate to "Credentials" tab
   - Copy "Secret"
4. **Configure Librislog:**
   ```bash
   OIDC_ENABLED=true
   OIDC_PROVIDER_NAME="Keycloak"
   OIDC_CLIENT_ID="librislog"
   OIDC_CLIENT_SECRET="<secret-from-keycloak>"
   OIDC_WELL_KNOWN_URL="https://keycloak.example.com/realms/myrealm/.well-known/openid-configuration"
   ```

### Azure AD / Microsoft Entra ID

1. **Register Application:**
   - Azure Portal → Azure Active Directory → App registrations → New registration
   - Name: `Librislog`
   - Redirect URI: `https://your-domain.com/api/oidc/callback`
2. **Configure API Permissions:**
   - Add: Microsoft Graph → Delegated → `openid`, `email`, `profile`
3. **Create Client Secret:**
   - Certificates & secrets → New client secret
4. **Get Tenant ID and Application ID**
5. **Configure Librislog:**
   ```bash
   OIDC_ENABLED=true
   OIDC_PROVIDER_NAME="Microsoft"
   OIDC_CLIENT_ID="<application-id>"
   OIDC_CLIENT_SECRET="<client-secret>"
   OIDC_WELL_KNOWN_URL="https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration"
   ```

### Google Workspace

1. **Create OAuth 2.0 Client:**
   - Google Cloud Console → APIs & Services → Credentials
   - Create credentials → OAuth client ID
   - Application type: Web application
   - Authorized redirect URIs:
     - `https://your-domain.com/api/oidc/callback`
     - `https://your-domain.com/api/oidc/link-callback`
2. **Configure Librislog:**
   ```bash
   OIDC_ENABLED=true
   OIDC_PROVIDER_NAME="Google"
   OIDC_CLIENT_ID="<client-id>.apps.googleusercontent.com"
   OIDC_CLIENT_SECRET="<client-secret>"
   OIDC_WELL_KNOWN_URL="https://accounts.google.com/.well-known/openid-configuration"
   ```

### Auth0

1. **Create Application:**
   - Auth0 Dashboard → Applications → Create Application
   - Application Type: Regular Web Application
2. **Configure Settings:**
   - Allowed Callback URLs:
     - `https://your-domain.com/api/oidc/callback`
     - `https://your-domain.com/api/oidc/link-callback`
3. **Get Domain, Client ID, and Secret**
4. **Configure Librislog:**
   ```bash
   OIDC_ENABLED=true
   OIDC_PROVIDER_NAME="Auth0"
   OIDC_CLIENT_ID="<client-id>"
   OIDC_CLIENT_SECRET="<client-secret>"
   OIDC_WELL_KNOWN_URL="https://<your-domain>.auth0.com/.well-known/openid-configuration"
   ```

## Troubleshooting

### "OIDC is not configured" Error
- Verify all environment variables are set
- Ensure `OIDC_ENABLED=true`
- Check that `.env` file is loaded (restart backend)

### "No 'sub' claim in OIDC token" Error
- Ensure `openid` scope is requested
- Check provider configuration includes `sub` claim

### "This account is already linked to another user"
- Each OIDC account can only be linked to one Librislog user
- Unlink the account from the other user first
- Or use a different OIDC account

### Redirect URI Mismatch
- Ensure redirect URIs in provider match exactly (including protocol and trailing slashes)
- Common issue: using `http://` vs `https://`
- For local testing, use `http://localhost:8000/api/oidc/callback`
```

## Rollout Checklist

- [ ] **Phase 1: Backend - Database Schema**
  - [ ] Add `OidcLink` model to `models.py`
  - [ ] Generate and apply Alembic migration
  - [ ] Verify migration in dev environment

- [ ] **Phase 2: Backend - Configuration**
  - [ ] Extend `Settings` in `config.py`
  - [ ] Update `.env.example` with OIDC variables
  - [ ] Test configuration loading

- [ ] **Phase 3: Backend - OIDC Integration**
  - [ ] Install `authlib` dependency
  - [ ] Create `backend/app/oidc.py`
  - [ ] Add OIDC schemas to `schemas.py`
  - [ ] Create `backend/app/routers/oidc.py`
  - [ ] Register OIDC router in `main.py`
  - [ ] Add session middleware
  - [ ] Test OIDC endpoints with mock provider

- [ ] **Phase 4: Frontend - UI Changes**
  - [ ] Add OIDC types to `types.ts`
  - [ ] Extend API client with OIDC methods
  - [ ] Update login page with OIDC button
  - [ ] Create OIDC callback handler page
  - [ ] Update profile page with linking section
  - [ ] Create OIDC link callback handler page
  - [ ] Add i18n translations (en, de)

- [ ] **Phase 5: Testing**
  - [ ] Write backend unit tests
  - [ ] Run backend test suite
  - [ ] Execute manual integration tests
  - [ ] Test with real OIDC provider (Keycloak/Google)

- [ ] **Phase 6: Documentation**
  - [ ] Update README with OIDC section
  - [ ] Create OIDC setup guide
  - [ ] Document provider-specific configurations

## Implementation Notes

### Session Management
The OIDC linking flow requires storing the user ID between the link initiation and callback. This uses Starlette's `SessionMiddleware`, which stores data in encrypted cookies.

**Security:** Session cookies are encrypted using the existing `API_KEY_ENCRYPTION_KEY` setting.

### Error Handling
OIDC errors are handled gracefully:
- **Provider errors**: Shown to user with provider's error message
- **Not linked**: User is informed and guided to link account
- **Already linked**: Prevents duplicate linkings
- **Missing config**: Returns 503 with clear message

### Frontend Routing
Two callback endpoints are needed:
1. `/auth/oidc/callback` - Handles login callback
2. `/auth/oidc/link-callback` - Handles account linking callback

Both pages handle the OAuth callback flow and display appropriate success/error messages.

### Multi-Provider Support (Future)
Current implementation supports one OIDC provider at a time. To support multiple providers:
1. Extend config to accept provider arrays
2. Modify UI to show multiple provider buttons
3. Update linking UI to manage multiple links
4. Add provider selection to login/link flows

## Security Considerations

1. **Session Security**: Session cookies use the existing encryption key and have a 1-hour expiration
2. **State Parameter**: Authlib automatically includes CSRF protection via the `state` parameter
3. **Token Validation**: Authlib validates OIDC tokens according to the spec
4. **No Password Storage**: OIDC accounts are linked by `sub` claim only; no OIDC tokens are stored
5. **Account Isolation**: Each OIDC `sub` can only link to one local user
6. **Primary Auth Preserved**: Email+password login always works regardless of OIDC status

## Future Enhancements

1. **Multiple Providers**: Support linking multiple OIDC providers per user
2. **Provider Icons**: Display provider-specific icons on login buttons
3. **Admin Provider Management**: UI for admins to configure OIDC providers
4. **Group/Role Mapping**: Map OIDC groups to Librislog roles
5. **JIT Provisioning** (Optional): Auto-create users on first OIDC login (configurable)
6. **OIDC Logout**: Implement OIDC logout (RP-initiated logout)
7. **Refresh Tokens**: Store and use refresh tokens for longer sessions
8. **MFA Requirements**: Enforce MFA via OIDC claims (`amr` claim)
