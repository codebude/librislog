from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.routers import auth, books, covers, import_, profile, users

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.covers_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="LibrisLog API",
    description="Backend API for LibrisLog.",
    lifespan=lifespan,
    openapi_url="/api/openapi.json",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(import_.router)
app.include_router(covers.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profile.router)


def _wrap_docs_html(html: str) -> HTMLResponse:
    custom_css = """
<style>
  :root {
    --bg: #f4f6f8;
    --surface: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --primary: #2563eb;
    --border: #e5e7eb;
  }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  }
  .topbar, .menu-content {
    display: none !important;
  }
  .swagger-ui .scheme-container,
  .swagger-ui .info,
  .swagger-ui .wrapper {
    background: transparent;
    box-shadow: none;
  }
  .swagger-ui .opblock,
  .swagger-ui .responses-inner,
  .swagger-ui .model-box,
  .swagger-ui .auth-container,
  .swagger-ui .dialog-ux {
    border-color: var(--border);
  }
  .swagger-ui .btn.execute,
  .swagger-ui .btn.authorize,
  .swagger-ui .btn.modal-btn.auth.authorize {
    background: var(--primary);
    border-color: var(--primary);
    color: #fff;
  }
  .swagger-ui .opblock-tag,
  .swagger-ui .opblock-summary,
  .swagger-ui .info .title,
  .swagger-ui,
  .swagger-ui p,
  .swagger-ui table,
  .swagger-ui .response-col_status,
  .swagger-ui .response-col_description {
    color: var(--text);
  }
  .swagger-ui .info .description,
  .swagger-ui .markdown p,
  .swagger-ui .markdown li,
  .swagger-ui .response-col_links,
  .swagger-ui .model-title small {
    color: var(--muted);
  }
  .redoc-wrap {
    background: var(--bg);
  }
  .redoc-wrap > div {
    border-left: 1px solid var(--border);
  }
</style>
"""
    return HTMLResponse(html.replace("</head>", f"{custom_css}</head>"))


@app.get("/api/docs", include_in_schema=False)
def custom_swagger_docs() -> HTMLResponse:
    html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "docExpansion": "list",
        },
    ).body.decode("utf-8")
    return _wrap_docs_html(html)


@app.get("/api/redoc", include_in_schema=False)
def custom_redoc_docs() -> HTMLResponse:
    html = get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
    ).body.decode("utf-8")
    return _wrap_docs_html(html)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
