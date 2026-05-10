from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import books, import_

app = FastAPI(title="LibrisLog API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(import_.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
