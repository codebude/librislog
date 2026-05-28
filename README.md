# LibrisLog

**Multi-user book tracking webapp** — maintain four reading lists (Want to Read, Currently Reading, Read, Did Not Finish), import books from Open Library & Google Books, scrape cover art, and manage your collection through a modern Svelte dashboard.

<p>
  <a href="https://codebude.github.io/librislog/">📚 Full Documentation</a>
  &nbsp;·&nbsp;
  <a href="https://codebude.github.io/librislog/guide/getting-started">Quick Start</a>
  &nbsp;·&nbsp;
  <a href="https://codebude.github.io/librislog/api/">API Reference</a>
  &nbsp;·&nbsp;
  <a href="https://codebude.github.io/librislog/next/">Nightly Docs</a>
</p>

[![Tests](https://github.com/codebude/librislog/actions/workflows/tests.yml/badge.svg)](https://github.com/codebude/librislog/actions/workflows/tests.yml)
[![Docker Build](https://github.com/codebude/librislog/actions/workflows/docker.yml/badge.svg)](https://github.com/codebude/librislog/actions/workflows/docker.yml)
[![Docs Build](https://github.com/codebude/librislog/actions/workflows/docs.yml/badge.svg)](https://codebude.github.io/librislog/)
![Python](https://img.shields.io/badge/python-3.14-%233776AB?logo=python)
![Svelte](https://img.shields.io/badge/svelte-5-%23FF3E00?logo=svelte)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-%23009688?logo=fastapi)
![License](https://img.shields.io/badge/license-MIT-green)

LibrisLog is a modern alternative to cloud-based book tracking services. You run it on your own server, own your data entirely, and get rich reading analytics without giving up privacy.

## Why LibrisLog?

- **Your data, your rules.** Fully self-hosted under MIT license — no ads, no tracking, no vendor lock-in. Your library is a single SQLite file you can back up anytime.
- **No API keys required.** Works with Open Library out of the box. Add Google Books or Hardcover.app tokens optionally for richer search results.
- **Rich insights from day one.** Calendar heatmap, language/status/page distribution charts, books finished per month/year, top authors — all computed on your hardware.
- **Multi-user from the start.** User roles (admin/user), optional OIDC SSO, per-user libraries. One instance works for your whole household or small group.
- **Import any format you have.** Goodreads CSV with automatic field mapping, generic CSV with per-field Python transforms, JSON, ZIP with covers. Your data is never locked in.
- **Point your phone at an ISBN barcode.** Real-time barcode scanning in the browser — no native app required.
- **Cover art from multiple sources.** Automatic search across AbeBooks, Open Library, Amazon, and Hardcover — plus manual upload or URL paste if the first hit isn't right.
- **Full REST API.** OpenAPI-documented backend you can script against — build your own frontend, connect home automation, or pipe data into your own tools.
- **Lightweight.** Two Docker containers, one SQLite database, one command: `docker compose up -d`.
- **Bilingual UI.** English and German with a localization framework ready for more languages.

## Features

- **Library** — Organize books into four statuses: Want to Read, Currently Reading, Read, Did Not Finish. Grid or list view, search and sort.
- **Reading progress** — Track page-level progress with a visual slider and a full progress timeline per book.
- **Statistics dashboard** — Pages read per month/year, books finished, language distribution, status breakdown, calendar heatmap, top authors.
- **Book import** — Search Open Library, Google Books, and Hardcover.app. Scan ISBN barcodes on mobile. Manual entry for anything not found.
- **Data portability** — Export as JSON, CSV, or ZIP with covers. Import from Goodreads CSV or any CSV with custom field mapping and Python transforms.
- **Cover management** — Automatic cover search from multiple sources with manual override, URL paste, or file upload.
- **Multi-user** — Admin/user roles, per-user libraries, optional OIDC login.
- **Themes** — Light, dark, and custom DaisyUI themes with persistent preferences.
- **Administration** — Full backup/restore of the SQLite database, user management, API key management.

<div>
  <a href="docs/public/screenshots/dashboard.png"><img src="docs/public/screenshots/dashboard-thumb.png" width="270" alt="Dashboard"></a>
  <a href="docs/public/screenshots/library-read.png"><img src="docs/public/screenshots/library-read-thumb.png" width="270" alt="Library"></a>
  <a href="docs/public/screenshots/statistics.png"><img src="docs/public/screenshots/statistics-thumb.png" width="270" alt="Statistics"></a>
</div>

## Quick Start

### Linux/macOS

```bash
mkdir librislog && cd librislog
curl -O https://raw.githubusercontent.com/codebude/librislog/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/codebude/librislog/main/.env.example
cp .env.example .env
sed -i "s/CHANGE_ME_TO_32PLUS_CHARS/$(openssl rand -base64 32)/" .env
docker compose up -d
```

### Windows

```powershell
mkdir librislog; cd librislog
Invoke-WebRequest -Uri https://raw.githubusercontent.com/codebude/librislog/main/docker-compose.yml -OutFile docker-compose.yml
Invoke-WebRequest -Uri https://raw.githubusercontent.com/codebude/librislog/main/.env.example -OutFile .env.example
Copy-Item .env.example .env
$key = [Convert]::ToBase64String([byte[]](1..32 | ForEach-Object {Get-Random -Maximum 256}))
(Get-Content .env).Replace('CHANGE_ME_TO_32PLUS_CHARS', $key) | Set-Content .env
docker compose up -d
```

Open **http://localhost:8001** and create your account.

## API

The backend is a standalone FastAPI application. You can run it independently and build your own frontend against it. The full API is documented via Swagger UI at `/api/docs` when the server is running.

Create API keys from the web UI (Profile → API Keys) for headless access — automation scripts, home integrations, or any programmatic use. See the [API Reference](https://codebude.github.io/librislog/api/) for details.

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI, SQLModel, SQLite, Alembic, Pydantic v2 |
| **Frontend** | Svelte 5, SvelteKit, Tailwind CSS v4, DaisyUI v5 |
| **Auth** | Session cookies, optional OIDC (Authlib) |
| **Deployment** | Docker, Docker Compose |
| **Package managers** | `uv` (Python), `npm` (Node) |
| **Testing** | pytest + pytest-cov (backend), Vitest + Testing Library (frontend), Playwright (E2E) |

## Contributing

See the [Developer Setup](https://codebude.github.io/librislog/guide/developer-setup) guide for instructions on running LibrisLog locally, running tests, and using the CLI tool.

This project was developed with the assistance of AI coding tools under a human-supervised workflow. No AI-generated code is committed without human review and approval.

## License

MIT

## Star History

<a href="https://www.star-history.com/?repos=codebude%2Flibrislog&type=date&legend=top-left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=codebude/librislog&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=codebude/librislog&type=date&legend=top-left" />
    <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=codebude/librislog&type=date&legend=top-left" />
  </picture>
</a>
