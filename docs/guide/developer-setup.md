# Developer Setup

For contributors who want to build from source or run individual services locally.

## Docker Compose (Local Builds)

Build and run both services from local source using the development compose file:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

This builds fresh images using your local checkout. The `docker-compose.dev.yml` file mirrors the default compose file but uses `build:` directives instead of pulling pre-built images.

### Build Arguments

When building, you can override these arguments:

| Argument | Description | Default |
|----------|-------------|---------|
| `APP_VERSION` | Application version string | `v0.0.0-dev` |
| `GIT_SHA` | Git commit hash for version display | `unknown` |
| `PUBLIC_DEFAULT_LOCALE` | Default UI language (`en` or `de`) | `en` |

Example:

```bash
export APP_VERSION="v1.0.0"
export GIT_SHA=$(git rev-parse --short HEAD)
export PUBLIC_DEFAULT_LOCALE="en"
docker compose -f docker-compose.dev.yml up -d --build
```

## Local Development — Backend

Requirements:
- Python 3.14+ (latest stable — install via [pyenv](https://github.com/pyenv/pyenv) if not available)
- `uv` package manager

Steps:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

The backend runs on http://localhost:8000 with auto-reload on code changes.

## Local Development — Frontend

Requirements:
- Node.js 20+ (see `frontend/.nvmrc`)

Steps:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on http://localhost:5173 and proxies `/api` requests to the backend.

### Version Injection

For production builds, the frontend embeds version information. Set these environment variables before building:

```bash
export APP_VERSION="v1.2.3"
export GIT_SHA="abc1234"
```

The version appears in the UI footer and is used for cache-busting.

## Running Tests

### Backend

```bash
cd backend
uv run pytest
```

### Frontend

```bash
cd frontend
npx vitest run
```
