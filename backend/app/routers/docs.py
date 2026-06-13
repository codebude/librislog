"""Custom Swagger UI and ReDoc documentation endpoints with CSS theming."""

import logging

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _wrap_docs_html(html: str) -> HTMLResponse:
    """Inject custom CSS into the Swagger/ReDoc HTML page for consistent theming."""
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


def _get_openapi_url(request: Request) -> str:
    """Return the OpenAPI URL relative to the current request, respecting root_path."""
    root_path = request.scope.get("root_path", "")
    return f"{root_path}/api/openapi.json"


@router.get("/docs", include_in_schema=False)
def redirect_to_custom_swagger_docs(request: Request) -> RedirectResponse:
    """Redirect to the custom-themed Swagger UI page."""
    root_path = request.scope.get("root_path", "")
    return RedirectResponse(url=f"{root_path}/api/docs")

@router.get("/api/docs", include_in_schema=False)
def custom_swagger_docs(request: Request) -> HTMLResponse:
    """Serve a custom-themed Swagger UI page."""
    openapi_url = _get_openapi_url(request)
    response = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=f"{request.app.title} - Swagger UI",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "docExpansion": "list",
        },
    )
    body = response.body.tobytes() if isinstance(response.body, memoryview) else response.body
    html = body.decode("utf-8")
    return _wrap_docs_html(html)

@router.get("/redoc", include_in_schema=False)
def redirect_to_custom_redoc_docs(request: Request) -> RedirectResponse:
    """Redirect to the custom-themed ReDoc page."""
    root_path = request.scope.get("root_path", "")
    return RedirectResponse(url=f"{root_path}/api/redoc")

@router.get("/api/redoc", include_in_schema=False)
def custom_redoc_docs(request: Request) -> HTMLResponse:
    """Serve a custom-themed ReDoc page."""
    openapi_url = _get_openapi_url(request)
    response = get_redoc_html(
        openapi_url=openapi_url,
        title=f"{request.app.title} - ReDoc",
    )
    body = response.body.tobytes() if isinstance(response.body, memoryview) else response.body
    html = body.decode("utf-8")
    return _wrap_docs_html(html)
