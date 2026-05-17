import logging

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/api/docs", include_in_schema=False)
def custom_swagger_docs(request: Request) -> HTMLResponse:
    html = get_swagger_ui_html(
        openapi_url=request.app.openapi_url,
        title=f"{request.app.title} - Swagger UI",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "docExpansion": "list",
        },
    ).body.decode("utf-8")
    return _wrap_docs_html(html)


@router.get("/api/redoc", include_in_schema=False)
def custom_redoc_docs(request: Request) -> HTMLResponse:
    html = get_redoc_html(
        openapi_url=request.app.openapi_url,
        title=f"{request.app.title} - ReDoc",
    ).body.decode("utf-8")
    return _wrap_docs_html(html)
