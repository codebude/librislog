# Plan: Timezone-Aware Frontend

## Problem & Requirement Summary

**Current Problem:**
- All date handling in the frontend (`date.ts`) treats ISO strings as UTC with no timezone awareness
- `today = new Date().toISOString().slice(0, 10)` uses UTC date — a user at UTC+2 at 01:00 sees yesterday as "today"
- `fromDateInputValue("2026-05-16")` → `"2026-05-16T00:00:00.000Z"` interprets the date as UTC midnight, but the user meant midnight in their timezone
- Backend `_validate_dates()` rejects dates > `datetime.now(timezone.utc)`, so a user in UTC+2 can't set "today" because it's "tomorrow" in UTC
- `formatDate()` and `formatDateTime()` display UTC timestamps, not local
- The SVG chart renders dates from `created_at.slice(0, 10)` which shows the UTC date part, not the user's local date

**Requirement:**
- Frontend should display and accept dates in the user's timezone
- Automatically detect browser timezone on first login/setup, save as user setting
- User can view/change timezone on the profile page
- Backend stays 100% UTC — no changes to backend date logic

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Browser / Frontend                                  │
│                                                      │
│  ┌─────────────┐    ┌──────────────────────────┐     │
│  │ timezone     │    │  date.ts (rewritten)      │     │
│  │ store        │◄──►│  - toDateInputValue(tz)   │     │
│  │ (rune/state) │    │  - fromDateInputValue(tz) │     │
│  └──────┬──────┘    │  - formatDate(tz)          │     │
│         │           │  - formatDateTime(tz)       │     │
│         │           │  - today(tz)                │     │
│         │           └────────┬─────────────────────┘     │
│         ▼                    ▼                           │
│  ┌──────────────────────────────────────────┐            │
│  │  Components                              │            │
│  │  BookDrawer, BookDetailDialog, Profile,  │            │
│  │  Setup, Login, OIDC Callback, i18n       │            │
│  └────────────────┬─────────────────────────┘            │
│                   │                                      │
└───────────────────┼──────────────────────────────────────┘
                    │ API (always UTC ISO strings)
┌───────────────────┼──────────────────────────────────────┐
│  Backend           ▼                                     │
│  ┌──────────────────────────────────┐                    │
│  │  FastAPI / SQLModel              │                    │
│  │  - UserSettings.timezone field   │                    │
│  │    (default "UTC")               │                    │
│  │  - All date storage: UTC         │                    │
│  └──────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Phase 1: Backend — Add `timezone` to UserSettings

**Files:**

| File | Change |
|------|--------|
| `backend/app/models.py` | Add `timezone: str = "UTC"` to `UserSettings` (max_length=64) |
| `backend/app/schemas.py` | Add `timezone: str` to `UserSettingsRead`; add `timezone: Optional[str]` to `UserSettingsUpdate` |
| `backend/alembic/versions/` | New migration: `ALTER TABLE usersettings ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'` |
| `backend/tests/test_auth_profile_users.py` | Add timezone tests |

---

### Phase 2: Frontend — Timezone Detection & Store

**Files to create/modify:**

| File | Change |
|------|--------|
| `frontend/src/lib/stores/timezone.ts` | **New file**. Detect/store user timezone as Svelte rune/store |
| `frontend/src/lib/types.ts` | Add `timezone: string` to `UserSettings` interface |
| `frontend/src/lib/api.ts` | Update `updateSettings()` type to accept `timezone?: string` |

**Timezone detection:** Use `dayjs.tz.guess()` (from the `dayjs` library with `utc` + `timezone` plugins). Fallback to `"UTC"`.

**Store initialization:**
- `frontend/src/routes/+layout.svelte` — init timezone context from user settings after load
- `frontend/src/routes/login/+page.svelte` — detect & save on first login
- `frontend/src/routes/setup/+page.svelte` — detect & save on setup
- `frontend/src/routes/auth/oidc/callback/+page.svelte` — detect & save after OIDC login

---

### Phase 3: Frontend — Rewrite Date Utilities

**File: `frontend/src/lib/date.ts`**

Use **Day.js** with `utc` and `timezone` plugins for all date operations:

```typescript
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
dayjs.extend(utc);
dayjs.extend(timezone);

// UTC ISO → YYYY-MM-DD in user's timezone
export function toDateInputValue(value, tz): string  // dayjs(value).tz(tz).format('YYYY-MM-DD')

// Local YYYY-MM-DD → UTC ISO string (for API)
export function fromDateInputValue(value, tz): string | null  // dayjs.tz(value, tz).toISOString()

// UTC ISO → localized display date — same as toDateInputValue
export function formatDate(value, tz): string

// UTC ISO → localized datetime
export function formatDateTime(value, tz): string  // dayjs(value).tz(tz).format('YYYY-MM-DD HH:mm')

// Today in user's timezone as YYYY-MM-DD
export function today(tz): string  // dayjs().tz(tz).format('YYYY-MM-DD')
```

Added npm dependency: `dayjs` (~6kB bundled with utc + timezone plugins).

---

### Phase 4: Frontend — Update All Consumers

| File | Changes |
|------|---------|
| `BookDrawer.svelte` | Pass `tz` to `toDateInputValue`, `fromDateInputValue`, `today`, `formatDate` |
| `BookDetailDialog.svelte` | Pass `tz` to `formatDate`, `formatDateTime`; fix chart labels via `formatDate` |
| `profile/+page.svelte` | Add timezone selector (full IANA list via `Intl.supportedValuesOf`) |
| `login/+page.svelte` | Detect & save timezone if default |
| `setup/+page.svelte` | Detect & save timezone if default |
| `+layout.svelte` | Init timezone store from settings |

---

### Phase 5: Profile Page — Timezone Selector

**Approach:** Use a native `<select>` populated dynamically from `Intl.supportedValuesOf('timeZone')` — this gives the **complete IANA timezone list** supported by the browser, which covers all valid timezones including exotic ones. No need for a curated subset.

**UX:**
- Group by region (Americas, Europe, Asia, Africa, Pacific, etc.) in the select
- Pre-select the user's current setting
- Show detected browser timezone as a note
- On change, call `api.profile.updateSettings({ timezone })` and update store

```typescript
const allTimezones = Intl.supportedValuesOf('timeZone');
// Group by region:
// Intl.DateTimeFormat('en', { timeZone: '...' })
//   .resolvedOptions().timeZone — always returns the canonical name
```

Fallback on serverside/SSR: provide a static list of all IANA timezones as a constant.

---

### Phase 6: i18n

| Key | EN | DE |
|-----|----|----|
| `settings.timezone` | Timezone | Zeitzone |
| `settings.timezoneHelp` | Display dates and times in your local timezone | Daten und Zeiten in Ihrer lokalen Zeitzone anzeigen |
| `settings.detected`  | Detected: {tz} | Erkannt: {tz} |

---

### Phase 7: Tests

**Backend:**
- `test_profile_settings_get_and_update` — verify `timezone` field
- verify default is `"UTC"`

**Frontend:**
- `src/lib/__tests__/date.test.ts` — test all tz-aware functions with known timezones

---

### Phase 8: Chart Label Fix

In `BookDetailDialog.svelte`, replace:
```typescript
e.created_at.slice(0, 10)  // UTC date part
```
with:
```typescript
formatDate(e.created_at, tz)  // user's local date
```

---

## Files Changed Summary

**Backend (5 files):**
- `backend/app/models.py` — +1 line
- `backend/app/schemas.py` — +2 lines
- `backend/alembic/versions/NNNN_add_timezone_to_usersettings.py` — new migration
- `backend/tests/test_auth_profile_users.py` — add timezone tests

**Frontend (14 files):**
- `frontend/src/lib/stores/timezone.ts` — **new**
- `frontend/src/lib/date.ts` — rewrite
- `frontend/src/lib/types.ts` — +1 line
- `frontend/src/lib/api.ts` — +1 line
- `frontend/src/lib/components/BookDrawer.svelte` — ~10 lines
- `frontend/src/lib/components/BookDetailDialog.svelte` — ~5 lines
- `frontend/src/routes/profile/+page.svelte` — ~30 lines
- `frontend/src/routes/login/+page.svelte` — ~5 lines
- `frontend/src/routes/setup/+page.svelte` — ~5 lines
- `frontend/src/routes/auth/oidc/callback/+page.svelte` — ~3 lines
- `frontend/src/routes/+layout.svelte` — ~5 lines
- `frontend/src/lib/i18n/locales/en.json` — 3 keys
- `frontend/src/lib/i18n/locales/de.json` — 3 keys
- `frontend/src/lib/__tests__/date.test.ts` — **new**

---

## Dependencies

- **New npm package:** `dayjs` (~6kB bundled with utc + timezone plugins) — handles all timezone-aware date conversions via `dayjs(value).tz(tz)` and `dayjs.tz(value, tz)`.
- No new Python packages
- `Intl.supportedValuesOf('timeZone')` — still used for profile page timezone list (Chrome 99+, Firefox 101+, Safari 15.4+)
- Fallback for SSR: empty array fallback if `Intl.supportedValuesOf` is unavailable
