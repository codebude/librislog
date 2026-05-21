# LibrisLog

**Single-user book tracking webapp** — maintain three reading lists (Want to Read, Currently Reading, Read), import books from Open Library & Google Books, scrape cover art, and manage your collection through a modern Svelte dashboard.

![Python](https://img.shields.io/badge/python-3.14-%233776AB?logo=python)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
![Svelte](https://img.shields.io/badge/svelte-5-%23FF3E00?logo=svelte)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-%23009688?logo=fastapi)
![License](https://img.shields.io/badge/license-MIT-green)
![Backend tests](https://img.shields.io/badge/tests-628_✔️-2ea44f?logo=pytest)
![Frontend tests](https://img.shields.io/badge/tests-290_✔️-2ea44f?logo=vitest)


## AI-Assisted Development Disclaimer

This project was developed with the assistance of AI coding tools (OpenCode CLI) under the following human-supervised workflow:

1. **Requirements engineering** — human specifies the feature
2. **Agent drafts** — AI agent generates an initial implementation for larger changes
3. **Plan review** — human reviews and corrects the plan iteratively
4. **Implementation** — agent writes code guided by the approved plan
5. **Code review** — agent runs a separate code-review AI model, reports findings
6. **Human review** — all changes are reviewed and corrected by a human before commit

No AI-generated code is committed without human review and approval.

---

## Quick Start (Docker)

```bash
cp .env.example .env          # review and adjust values
docker compose up --build -d
```

The frontend is available at **http://localhost:8001** and the API at **http://localhost:8000**. Health check: `GET /api/health`.

---

## Configuration

All configuration is done through the `.env` file in the project root. See `.env.example` for defaults.

### Core

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/librislog.db` | SQLite database path |
| `CORS_ORIGINS` | `["http://localhost", …]` | Allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Python log level |
| `API_KEY_ENCRYPTION_KEY` | — | **Required.** 32+ char secret for API key encryption |
| `FORWARDED_ALLOW_IPS` | `*` | Trusted proxy IPs for forwarded headers. `*` trusts all (recommended behind your own TLS proxy). Set to specific IPs to restrict. |

### Authentication

| Variable | Default | Description |
|---|---|---|
| `AUTH_COOKIE_NAME` | `librislog_session` | Session cookie name |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` in production (HTTPS) |
| `AUTH_COOKIE_SAMESITE` | `lax` | `lax` \| `strict` \| `none` |

### OIDC (optional)

| Variable | Default | Description |
|---|---|---|
| `OIDC_ENABLED` | `false` | Enable OpenID Connect login |
| `OIDC_CLIENT_ID` | — | OIDC client ID |
| `OIDC_CLIENT_SECRET` | — | OIDC client secret |
| `OIDC_WELL_KNOWN_URL` | — | OIDC discovery URL |

### Book import

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_BOOKS_API_KEY` | — | Google Books API key (required for Google fallback) |
| `HARDCOVER_APP_API_TOKEN` | — | Hardcover.app API token (optional source) |

### Cover scraping

| Variable | Default | Description |
|---|---|---|
| `COVERS_DIR` | `./data/covers` | Local cover image storage directory |
| `THALIA_COVER_SEARCH_ENABLED` | `false` | Enable Thalia.de cover scraping. **Research-only:** users must ensure compliance with Thalia's ToS. The author assumes no liability for misuse. |

### Dashboard

| Variable | Default | Description |
|---|---|---|
| `DASHBOARD_QUOTE_ENABLED` | `true` | Show motivational quote on dashboard |
| `DASHBOARD_QUOTE_URL` | *(spark API)* | Quote API endpoint |
| `DASHBOARD_QUOTE_CACHE_TTL` | `86400` | Quote cache TTL in seconds |

### Frontend (build-time)

| Variable | Default | Description |
|---|---|---|
| `PUBLIC_DEFAULT_LOCALE` | `en` | UI default locale: `en` \| `de` |

### Build-time version injection

```bash
export APP_VERSION=$(git describe --tags --always)
export GIT_SHA=$(git rev-parse HEAD)
docker compose up --build -d
```

Omitting these vars leaves the fallback `v0.0.0-dev` / `unknown`. Version is shown in the sidebar and exposed on the health endpoint.

---

## Development

### Prerequisites

- Python 3.14+
- Node.js 26+ — use `nvm use` inside `frontend/` (`.nvmrc` is provided)
- [uv](https://github.com/astral-sh/uv)

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload          # http://localhost:8000
```

All routes are documented at `/docs` (Swagger UI) when the server is running.

### Frontend

```bash
cd frontend
nvm use
npm install
npm run dev                                     # http://localhost:5173
```

The dev server proxies `/api` requests to `http://localhost:8000`.

---

## Testing

### Backend (pytest, 628 tests)

```bash
cd backend
uv run pytest                                   # runs tests with coverage
```

### Frontend (Vitest, 290 tests)

```bash
cd frontend
npm test                                        # runs tests
npm run test:coverage                           # runs tests with coverage report
```

### Frontend type-checking (Svelte validation)

```bash
cd frontend
npm run check                                   # runs svelte-check
```

---

## Project Structure

```
librislog/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # pydantic-settings configuration
│   │   ├── models.py               # SQLModel ORM models
│   │   ├── schemas.py              # Pydantic request/response schemas
│   │   ├── database.py             # DB engine & session dependency
│   │   ├── auth.py                 # Authentication & session logic
│   │   ├── oidc.py                 # OpenID Connect integration
│   │   ├── routers/                # API route handlers
│   │   │   ├── books.py            # Book CRUD
│   │   │   ├── auth.py             # Login/logout
│   │   │   ├── covers.py           # Cover upload/import
│   │   │   ├── cover_candidates.py # Auto-search covers by ISBN
│   │   │   ├── data.py             # Data export/import
│   │   │   ├── import_.py          # Book import (Open Library, Google Books)
│   │   │   ├── progress.py         # Reading progress
│   │   │   ├── statistics.py       # Dashboard statistics
│   │   │   ├── profile.py          # User profile & settings
│   │   │   ├── admin.py            # Admin endpoints
│   │   │   ├── users.py            # User management
│   │   │   ├── health.py           # Health check
│   │   │   └── docs.py             # Documentation routes
│   │   └── services/               # Business logic
│   │       ├── book_import.py      # Open Library & Google Books search
│   │       ├── cover_import.py     # Cover download & processing
│   │       ├── cover_storage.py    # Local cover file storage
│   │       ├── data_export.py      # Export to JSON/CSV/ZIP
│   │       ├── data_import.py      # Import from JSON/CSV
│   │       ├── backup_restore.py   # Full DB backup & restore
│   │       ├── tags.py             # Tag management
│   │       ├── quote_cache.py      # Dashboard quote caching
│   │       ├── isbn_utils.py       # ISBN-10/13 conversion
│   │       └── user_deletion.py    # Account deletion
│   ├── alembic/                    # Database migrations
│   ├── tests/                      # 628 pytest tests
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts              # Typed fetch wrappers
│   │   │   ├── types.ts            # TypeScript interfaces
│   │   │   ├── toasts.ts           # Toast notification store
│   │   │   ├── i18n/               # Internationalisation (en, de)
│   │   │   ├── stores/             # Svelte stores (auth, timezone)
│   │   │   ├── components/         # 27 Svelte components (41 files incl. tests)
│   │   │   └── test/               # Test setup & mocks
│   │   └── routes/                 # SvelteKit pages
│   └── Dockerfile
├── docker-compose.yml              # 2 services: backend + frontend
└── .env.example                    # All configurable variables
```

## Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI, SQLModel, SQLite, Alembic, Pydantic v2 |
| **Frontend** | Svelte 5, SvelteKit, Tailwind CSS v4, DaisyUI v5 |
| **Auth** | Session cookies, optional OIDC (Authlib) |
| **Reverse proxy** | nginx (embedded in frontend container) |
| **Package managers** | `uv` (Python), `npm` (Node) |
| **Testing** | pytest + pytest-cov (backend), Vitest + Testing Library (frontend) |
