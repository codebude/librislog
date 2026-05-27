# LibrisLog

**Multi-user book tracking webapp** — maintain four reading lists (Want to Read, Currently Reading, Read, Did Not Finish), import books from Open Library & Google Books, scrape cover art, and manage your collection through a modern Svelte dashboard.

<p>
  <a href="https://codebude.github.io/librislog/">📚 Full Documentation</a>
  &nbsp;·&nbsp;
  <a href="https://codebude.github.io/librislog/guide/getting-started">Quick Start</a>
  &nbsp;·&nbsp;
  <a href="https://codebude.github.io/librislog/api/">API Reference</a>
</p>

[![Tests](https://github.com/codebude/librislog/actions/workflows/tests.yml/badge.svg)](https://github.com/codebude/librislog/actions/workflows/tests.yml)
[![Docker Build](https://github.com/codebude/librislog/actions/workflows/docker.yml/badge.svg)](https://github.com/codebude/librislog/actions/workflows/docker.yml)
[![Docs Build](https://github.com/codebude/librislog/actions/workflows/docs.yml/badge.svg)](https://codebude.github.io/librislog/)
![Python](https://img.shields.io/badge/python-3.14-%233776AB?logo=python)
![Svelte](https://img.shields.io/badge/svelte-5-%23FF3E00?logo=svelte)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-%23009688?logo=fastapi)
![License](https://img.shields.io/badge/license-MIT-green)

<div>
  <a href="docs/public/screenshots/dashboard.png"><img src="docs/public/screenshots/dashboard-thumb.png" width="400" alt="Dashboard"></a>
  <a href="docs/public/screenshots/library-read.png"><img src="docs/public/screenshots/library-read-thumb.png" width="400" alt="Library"></a>
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

The backend is a standalone FastAPI application. You can run it independently and build your own frontend against it. The API is documented via Swagger UI at `/api/docs` when the server is running.

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
| **Package managers** | `uv` (Python), `npm` (Node) |
| **Testing** | pytest + pytest-cov (backend), Vitest + Testing Library (frontend) |

## Star History

<a href="https://www.star-history.com/?repos=codebude%2Flibrislog&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=codebude/librislog&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=codebude/librislog&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=codebude/librislog&type=date&legend=top-left" />
 </picture>
</a>

---

## AI-Assisted Development Disclaimer

This project was developed with the assistance of AI coding tools (OpenCode CLI) under a human-supervised workflow. No AI-generated code is committed without human review and approval.

## License

MIT
