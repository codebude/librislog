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
| `PUBLIC_DEFAULT_LOCALE` | Default UI language (`en`, `de`, `zh`, `es`, or `fr`) | `en` |

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

## Documentation

The VitePress documentation lives in the `docs/` directory:

```
docs/
├── index.md              # Landing page
├── about.md              # About page
├── guide/                # User-facing guides
│   ├── getting-started.md
│   ├── developer-setup.md
│   ├── configuration.md
│   ├── api-keys.md
│   ├── cli.md
│   └── using-librislog/  # Feature-specific guides
├── api/                  # API documentation
│   ├── index.md
│   └── setup.md
└── public/               # Static assets (screenshots, favicon)
```

### Dev Server

```bash
cd docs
npm install
npm run docs:dev
```

Opens on http://localhost:5174 with hot reload.

### Production Build

```bash
npm run docs:build
```

Output goes to `docs/.vitepress/dist/`.

### Nightly Docs

The CI workflow publishes two doc sets on every push to `develop`:
- **Release docs** at `https://docs.librislog.app/` — built from the latest git tag
- **Nightly docs** at `https://docs.librislog.app/next/` — built from `develop`

The nightly build uses a separate config (`config.nightly.ts`) which sets a different base path and swaps the nav link to point back to the release docs.

## Running Tests

All test suites can also be run via the [developer CLI](cli.md).

### Backend

```bash
cd backend
uv run pytest
# or:  uv run llc test backend
```

### CLI

```bash
cd cli
uv run pytest
# or:  uv run llc test cli
```

### Frontend (Unit)

```bash
cd frontend
npx vitest run
# or:  uv run llc test frontend
```

### E2E (Playwright)

End-to-end tests run the full stack (backend + frontend) inside Docker containers using `docker-compose.e2e.yml`. A Playwright test-runner container drives the browser against the real services.

```bash
cd frontend
npm run test:e2e
# or:  uv run llc test e2e
```

### All Suites

```bash
uv run llc test all
```

This runs backend, CLI, frontend unit, and E2E tests sequentially and prints a summary.
