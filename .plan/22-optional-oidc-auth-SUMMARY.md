# Summary: Optional OIDC Authentication Support

## Overview
Adds optional OpenID Connect (OIDC) authentication for enterprise SSO integration while maintaining email+password as the primary authentication method.

## Key Design Principles
1. **OIDC is secondary auth** - Not a first-class authentication provider
2. **Manual linking required** - Users must link OIDC accounts to existing accounts
3. **No OIDC registration** - Account creation still via admin UI only
4. **Always allow password login** - Email+password works even when OIDC is active
5. **Environment-only config** - OIDC configured via env vars, not UI

## Architecture

### Database
- New `OidcLink` table linking users to OIDC provider accounts
- Stores: `user_id`, `provider_name`, `oidc_sub`, `oidc_email`, `oidc_name`
- Unique constraints prevent duplicate linkings

### Backend
- **Config**: `oidc_enabled`, `oidc_provider_name`, `oidc_client_id`, `oidc_client_secret`, `oidc_well_known_url`
- **New module**: `backend/app/oidc.py` - OAuth client initialization
- **New router**: `backend/app/routers/oidc.py` - OIDC endpoints
- **Endpoints**:
  - `GET /api/oidc/config` - Public config for frontend
  - `GET /api/oidc/login` - Initiate OIDC login
  - `GET /api/oidc/callback` - Handle login callback
  - `GET /api/oidc/link-status` - Check link status (auth required)
  - `POST /api/oidc/link` - Initiate account linking (auth required)
  - `GET /api/oidc/link-callback` - Handle linking callback
  - `DELETE /api/oidc/unlink` - Unlink account (auth required)
- **Dependencies**: Adds `authlib>=1.3.0`
- **Session middleware**: Required for linking flow state management

### Frontend
- **Login page**: Shows OIDC button when enabled
- **Profile page**: OIDC linking section with link/unlink functionality
- **Callback pages**:
  - `/auth/oidc/callback` - Login callback handler
  - `/auth/oidc/link-callback` - Linking callback handler
- **i18n**: English and German translations for OIDC UI

## User Workflows

### Initial Setup (Admin)
1. Configure OIDC provider (Keycloak, Azure AD, Auth0, etc.)
2. Add environment variables to `.env`
3. Restart backend

### User Login Flow - First Time
1. Admin creates user account
2. User logs in with email+password
3. User navigates to profile
4. User clicks "Link [Provider] account"
5. User authenticates with OIDC provider
6. Account is linked
7. User can now login via OIDC or email+password

### User Login Flow - With Linked Account
1. User clicks "Login with [Provider]" on login page
2. User authenticates with OIDC provider
3. User is logged in automatically

### Unlinked OIDC Login Attempt
1. User clicks "Login with [Provider]"
2. User authenticates with OIDC provider
3. Error: "Your [Provider] account is not linked..."
4. User is instructed to login with email+password and link account

## Implementation Phases

1. **Database Schema** - Add `OidcLink` table via Alembic migration
2. **Backend Config** - Extend settings, update `.env.example`
3. **Backend OIDC** - Install authlib, create OIDC module and router
4. **Frontend UI** - Update login page, profile page, add callback handlers
5. **Testing** - Unit tests, integration tests with real provider
6. **Documentation** - README, OIDC setup guide for various providers

## Testing Approach

### Unit Tests
- OIDC config endpoint (enabled/disabled)
- Login callback with linked/unlinked accounts
- Link status endpoint
- Account linking/unlinking
- Duplicate linking prevention

### Integration Tests
- Full login flow with test OIDC provider
- Account linking flow
- Unlinking flow
- Email+password login still works with OIDC enabled

## Security

- Session cookies encrypted with existing `API_KEY_ENCRYPTION_KEY`
- CSRF protection via OAuth `state` parameter (handled by Authlib)
- OIDC token validation per spec (handled by Authlib)
- No OIDC tokens stored permanently (only during callback)
- Each OIDC `sub` can only link to one local user
- Email+password login always available

## Provider Support

Supports any OpenID Connect 1.0 compliant provider:
- Keycloak
- Azure AD / Microsoft Entra ID
- Auth0
- Okta
- Google Workspace
- Custom OIDC providers

## Future Enhancements

- Multiple providers per installation
- Provider icons on login buttons
- Admin UI for provider management
- OIDC group/role mapping
- Optional JIT (Just-In-Time) user provisioning
- OIDC logout (RP-initiated)
- Refresh token support
- MFA enforcement via OIDC claims

## Files Modified/Created

### Backend
- **Modified**: `backend/app/models.py` (add `OidcLink`)
- **Modified**: `backend/app/config.py` (add OIDC settings)
- **Modified**: `backend/app/schemas.py` (add OIDC schemas)
- **Modified**: `backend/app/main.py` (register router, add session middleware)
- **Modified**: `backend/pyproject.toml` (add authlib)
- **Modified**: `.env.example` (add OIDC vars)
- **Created**: `backend/app/oidc.py`
- **Created**: `backend/app/routers/oidc.py`
- **Created**: `backend/alembic/versions/XXXX_add_oidc_link_table.py`
- **Created**: `backend/tests/test_oidc.py`

### Frontend
- **Modified**: `frontend/src/lib/types.ts` (add OIDC types)
- **Modified**: `frontend/src/lib/api.ts` (add OIDC methods)
- **Modified**: `frontend/src/routes/login/+page.svelte` (add OIDC button)
- **Modified**: `frontend/src/routes/profile/+page.svelte` (add OIDC linking section)
- **Modified**: `frontend/src/lib/i18n/en.json` (add translations)
- **Modified**: `frontend/src/lib/i18n/de.json` (add translations)
- **Created**: `frontend/src/routes/auth/oidc/callback/+page.svelte`
- **Created**: `frontend/src/routes/auth/oidc/link-callback/+page.svelte`

### Documentation
- **Modified**: `README.md` (add OIDC section)
- **Created**: `docs/oidc-setup-guide.md`
- **Created**: `.plan/22-optional-oidc-auth-test-scenarios.md`

## Effort Estimate

- **Backend implementation**: ~4-6 hours
- **Frontend implementation**: ~3-4 hours
- **Testing**: ~2-3 hours
- **Documentation**: ~1-2 hours
- **Total**: ~10-15 hours

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Session middleware conflicts | Medium | Use existing encryption key, test thoroughly |
| Provider compatibility issues | Medium | Test with multiple providers, document quirks |
| User confusion about linking | Low | Clear UI messaging, comprehensive error messages |
| Duplicate account linking bugs | Medium | Database constraints, thorough testing |
| Session cookie size limits | Low | Store minimal data in session |

## Rollout Plan

1. **Development**: Implement phases 1-4
2. **Testing**: Execute unit and integration tests
3. **Documentation**: Complete setup guides
4. **Staging**: Deploy to staging with test OIDC provider
5. **Validation**: Test with real users
6. **Production**: Enable OIDC for production environment
7. **Monitoring**: Watch for auth errors, user feedback
