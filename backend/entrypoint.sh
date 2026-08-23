#!/bin/sh
set -e
export ALEMBIC_CONFIG=/app/backend/alembic.ini
uv run --no-project alembic upgrade head
exec uv run --no-project uvicorn app.main:app --host 0.0.0.0 --port 8000
