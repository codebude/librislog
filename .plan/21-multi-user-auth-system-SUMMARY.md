# Multi-User Authentication & Authorization System - Summary

## Overview
Add full multi-user authentication and authorization to LibrisLog, enabling isolated user data, role-based access control (admin/user), first-time setup flow, API-key based authentication, and user profile management.

## Key Features
- **User authentication** via email/password for login + API key authorization for API requests
- **Role-based authorization** (admin vs. user)
- **Data isolation**: each user sees only their own books
- **Cover isolation**: stored cover filenames include `user_id` scope to prevent cross-user collisions/deletes
- **Setup page**: Initial admin account creation when no users exist
- **User management**: Admins can create/delete users (but not themselves)
- **User profile**: Edit name, email, and language preference (moved from settings)
- **API key management**: per-user main API key + additional keys with note/description
- **UI updates**: User avatar bubble with dropdown (profile, logout)

## Impacts
- **Breaking change**: Existing book data will be associated with the first admin user created during setup
- **Database schema**: New `users`, `user_settings` tables; `books` gains `user_id` foreign key
- **Database schema (extra)**: New `api_keys` table mapped to users
- **API**: All protected endpoints require `X-API-Key`; new `/auth`, `/users`, `/profile`, `/profile/api-keys` endpoints
- **Frontend**: New `/setup`, `/login`, `/profile` routes; route guards; language settings migrated to user profile; API key management UI
- **Testing**: Authentication fixtures, role-based authorization tests, setup flow tests

## Phases
1. **Backend Auth Foundation** (User model, password hashing, API key generation/verification)
2. **Database Migration & Data Association** (Alembic migration, user_id on books, `api_keys` table, setup detection)
3. **Backend Authorization** (dependency injection via API key, role checks, book ownership enforcement)
4. **Backend API Endpoints** (login/bootstrap + profile/admin + API key CRUD)
5. **Frontend Authentication UI** (setup/login/logout, route guards, API key storage for active session)
6. **Frontend User Profile & Settings Migration** (profile page, avatar dropdown, language DB persistence, API key management)
7. **Testing & Documentation** (unit/integration/E2E + security and key rotation notes)

## Risks & Mitigations
- **Data migration**: Existing books must be assigned to a user → migration script will create a default admin if needed
- **API key security**: additional keys are hash-only; the main app key is stored recoverably (encrypted-at-rest) so it can be re-read when needed
- **Lockout prevention**: Admins cannot delete themselves; setup page is gated to prevent re-creation
- **Breaking API changes**: All clients must authenticate → version API or coordinate deployment
- **Cover collision risk**: Prefix/scope stored cover files by `user_id` and enforce ownership on cleanup
