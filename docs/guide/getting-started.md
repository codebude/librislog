# Quick Start

Get LibrisLog running in minutes.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (includes Docker Compose)
- `curl` or `wget` (to download files)

## Setup

Download the files, create your environment, and generate a secure encryption key:

```bash
mkdir librislog && cd librislog \
  && curl -O https://raw.githubusercontent.com/codebude/librislog/main/docker-compose.yml \
  && curl -O https://raw.githubusercontent.com/codebude/librislog/main/.env.example \
  && cp .env.example .env \
  && sed -i "s/CHANGE_ME_TO_32PLUS_CHARS/$(openssl rand -base64 32)/" .env
```

> The `.env` file can be further customized — see [Configuration](/guide/configuration) for all available options.

Start the application:

```bash
docker compose up -d
```

Open http://localhost:8001 in your browser.

## First-Time Setup

On first launch, create a user account through the web interface.

![Dashboard](/screenshots/dashboard.png)

The dashboard shows your currently reading books, reading progress, and a random inspirational quote.

## Verification

Check that the application is healthy:

```bash
curl http://localhost:8000/api/health
```

You should see a JSON response with status information.
