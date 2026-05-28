# Quick Start

Get LibrisLog running in minutes.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (includes Docker Compose)
- `curl` or `wget` (to download files)

## Setup

Download the files, create your environment, and generate a secure encryption key.

::: code-group

```bash [Linux/macOS]
mkdir librislog && cd librislog \
  && curl -O https://raw.githubusercontent.com/codebude/librislog/main/docker-compose.yml \
  && curl -O https://raw.githubusercontent.com/codebude/librislog/main/.env.example \
  && cp .env.example .env \
  && sed -i "s/CHANGE_ME_TO_32PLUS_CHARS/$(openssl rand -base64 32)/" .env
```

```powershell [Windows]
mkdir librislog; cd librislog
Invoke-WebRequest -Uri https://raw.githubusercontent.com/codebude/librislog/main/docker-compose.yml -OutFile docker-compose.yml
Invoke-WebRequest -Uri https://raw.githubusercontent.com/codebude/librislog/main/.env.example -OutFile .env.example
Copy-Item .env.example .env
$key = [Convert]::ToBase64String([byte[]](1..32 | ForEach-Object {Get-Random -Maximum 256}))
(Get-Content .env).Replace('CHANGE_ME_TO_32PLUS_CHARS', $key) | Set-Content .env
```

:::

> **Alternative key generation**: If you don't have OpenSSL or PowerShell, run `python -c "import secrets; print(secrets.token_urlsafe(32))"` or use an online generator like [base64encode.org](https://www.base64encode.org/) (generate 32 random bytes, encode to base64). Then manually replace `CHANGE_ME_TO_32PLUS_CHARS` in your `.env` file.

> The `.env` file can be further customized — see [Configuration](/guide/configuration) for all available options.

Start the application:

```bash
docker compose up -d
```

The backend API will be available at http://localhost:8000 and the frontend at http://localhost:8001.

## First-Time Setup

On first launch, create a user account through the web interface at http://localhost:8001.

![Dashboard](/screenshots/dashboard.png)

The dashboard shows your currently reading books, reading progress, and a random inspirational quote.

## Verification

Check that the application is healthy:

```bash
curl http://localhost:8000/api/health
```

You should see a JSON response with status information.

You can also verify the frontend is accessible by opening http://localhost:8001 in your browser.
