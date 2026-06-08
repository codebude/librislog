# Configuration

All configuration is done via environment variables in a `.env` file at the project root.

## Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database file path | `sqlite:///./data/librislog.db` |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array or comma-separated) | `["http://localhost", "http://localhost:5173", "http://localhost:4173"]` |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `API_KEY_ENCRYPTION_KEY` | Secret key for API key encryption (must be real, not placeholder) | Requires 32+ characters |
| `FORWARDED_ALLOW_IPS` | Trusted proxy IPs | `*` |

## Authentication

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_COOKIE_NAME` | Session cookie name | `librislog_session` |
| `AUTH_COOKIE_SECURE` | Use secure cookies (HTTPS only) | `false` |
| `AUTH_COOKIE_SAMESITE` | SameSite cookie attribute | `lax` |
| `AUTH_COOKIE_DOMAIN` | Cookie domain | — |

## OIDC (Optional)

| Variable | Description |
|----------|-------------|
| `OIDC_ENABLED` | Enable OIDC authentication (`true`/`false`) |
| `OIDC_CLIENT_ID` | OIDC client ID |
| `OIDC_CLIENT_SECRET` | OIDC client secret |
| `OIDC_WELL_KNOWN_URL` | OIDC well-known configuration URL |

## Book Import Sources

| Variable | Description |
|----------|-------------|
| `GOOGLE_BOOKS_API_KEY` | Google Books API key (see [API Keys](/guide/api-keys)) | 
| `HARDCOVER_APP_API_TOKEN` | Hardcover.app API token (see [API Keys](/guide/api-keys)) |

## Cover Scraping

| Variable | Description | Default |
|----------|-------------|---------|
| `COVERS_DIR` | Directory for cached cover images | `./data/covers` |
| `THALIA_COVER_SEARCH_ENABLED` | Enable Thalia cover search | `false` |

> **Disclaimer:** Enabling Thalia cover search uses automated scraping of thalia.de. This likely violates their Terms of Service. The app ships with this feature disabled by default. Enable it only for research purposes and at your own risk. Do not use in production.

## Dashboard

| Variable | Description | Default |
|----------|-------------|---------|
| `DASHBOARD_QUOTE_ENABLED` | Enable dashboard quote | `true` |
| `DASHBOARD_QUOTE_URL` | Quote API endpoint | `https://motivational-spark-api.vercel.app/api/quotes/random` |
| `DASHBOARD_QUOTE_CACHE_TTL` | Quote cache time-to-live (seconds) | `86400` |

## Frontend Build

| Variable | Description | Default |
|----------|-------------|---------|
| `PUBLIC_DEFAULT_LOCALE` | Default UI language (`en`, `de`, `zh`, `es`, or `fr`) | `en` |

## Import Limits

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_IMPORT_FILE_SIZE_MB` | Maximum import file size (MB) | `100` |
| `MAX_IMPORT_ROW_COUNT` | Maximum import row count | `10000` |

## Validation Rules

- `API_KEY_ENCRYPTION_KEY` must be a real secret key (minimum 32 characters). Do not use the placeholder value from `.env.example`. If left as placeholder or set to a weak value, API key creation will fail.
- When `OIDC_ENABLED=true`, all three OIDC variables must be set.
- `GOOGLE_BOOKS_API_KEY` and `HARDCOVER_APP_API_TOKEN` are optional. See [API Keys](/guide/api-keys) for how to obtain them. The app runs fine without them using Open Library.

## Example .env

```bash
DATABASE_URL=sqlite:///./data/librislog.db
CORS_ORIGINS=["http://localhost", "http://localhost:5173", "http://localhost:4173"]
LOG_LEVEL=INFO
API_KEY_ENCRYPTION_KEY=  # CHANGE ME: generate with `openssl rand -base64 32`
FORWARDED_ALLOW_IPS=*

AUTH_COOKIE_NAME=librislog_session
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax

GOOGLE_BOOKS_API_KEY=your-google-books-api-key
HARDCOVER_APP_API_TOKEN=your-hardcover-token

COVERS_DIR=./data/covers
THALIA_COVER_SEARCH_ENABLED=false

DASHBOARD_QUOTE_ENABLED=true
DASHBOARD_QUOTE_URL=https://motivational-spark-api.vercel.app/api/quotes/random
DASHBOARD_QUOTE_CACHE_TTL=86400

PUBLIC_DEFAULT_LOCALE=en
MAX_IMPORT_FILE_SIZE_MB=100
MAX_IMPORT_ROW_COUNT=10000
```