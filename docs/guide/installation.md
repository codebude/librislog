# Installation

## Docker Compose (Recommended)

The simplest way to run LibrisLog is with Docker Compose, which starts both the backend and frontend services.

### docker-compose.yml Overview

The compose file defines two services:
- **backend**: FastAPI application with SQLite database
- **frontend**: SvelteKit application served via Node.js

Volumes:
- `./data:/app/data` — Persistent database and uploads
- `./frontend:/app/frontend` — Frontend source (dev mode)

### Build Arguments

When building, set these arguments:
- `APP_VERSION` — Application version string
- `GIT_SHA` — Git commit hash for version display
- `PUBLIC_DEFAULT_LOCALE` — Default UI language (`en` or `de`)

Example:
```bash
export APP_VERSION="v1.0.0"
export GIT_SHA=$(git rev-parse --short HEAD)
export PUBLIC_DEFAULT_LOCALE="en"
docker compose up --build -d
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

## Version Injection

For production builds, the frontend embeds version information. Set these environment variables before building:

```bash
export APP_VERSION="v1.2.3"
export GIT_SHA="abc1234"
```

The version appears in the UI footer and is used for cache-busting.