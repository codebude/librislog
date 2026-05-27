# Getting Started

Get LibrisLog running in minutes with Docker Compose.

## Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development only)

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/codebude/librislog.git
cd librislog
```

2. Copy the environment file:
```bash
cp .env.example .env
```

3. Start the application:
```bash
docker compose up --build -d
```

4. Access the application:
- Frontend: http://localhost:8001
- API: http://localhost:8000
- API Docs (Swagger UI): http://localhost:8000/api/docs

## First-Time Setup

On first launch, create a user account through the web interface. The application uses local authentication by default. OIDC integration is available via environment configuration.

![Dashboard](/screenshots/dashboard.png)

The dashboard shows your currently reading books, reading progress, and a random inspirational quote.

## Development Mode

For local development with hot reloading:

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The frontend dev server runs on http://localhost:5173 and proxies API requests to localhost:8000.

## Verification

Check that the application is healthy:

```bash
curl http://localhost:8000/api/health
```

You should see a JSON response with status information.