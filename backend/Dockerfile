FROM python:3.14-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace dependency files first for layer caching.
# The backend is a uv workspace member, so the lockfile lives at the repo root.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml ./backend/

# Sync only the backend workspace member's production dependencies.
# The workspace root keeps the lockfile, so we build from the repo root context.
RUN uv sync --project backend --no-dev --frozen

# Copy application source
COPY backend/alembic.ini ./backend/
COPY backend/alembic/ ./backend/alembic/
COPY backend/app/ ./backend/app/

# Make the backend source importable from the workspace root
ENV PYTHONPATH=/app/backend

# Inject version from build args (overwrites fallback in _build_info.py)
ARG APP_VERSION=v0.0.0-dev
ARG GIT_SHA=unknown
RUN echo "__version__ = \"$APP_VERSION\"" > ./backend/app/_build_info.py && \
    echo "__git_sha__ = \"$GIT_SHA\"" >> ./backend/app/_build_info.py

# Entrypoint: run migrations then start server
COPY backend/entrypoint.sh ./backend/
RUN chmod +x ./backend/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./backend/entrypoint.sh"]
