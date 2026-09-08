"""FastAPI application entry point.

Phase 1 scope: the app is stateless (hard rule #2). No module-level mutable state,
no in-RAM sessions, no caches — anything that must survive a request goes to
Postgres or Redis.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import get_settings
from app.logging import configure_logging, request_id_middleware

configure_logging()

app = FastAPI(title="SocialOps API", version="0.1.0")

# One structured JSON line per request, tagged with request_id (hard rule #8).
app.middleware("http")(request_id_middleware)

# The browser calls the API directly from the Next.js app on another origin.
# Phase 1 has no auth and no cookies, so a permissive policy costs nothing here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Health(BaseModel):
    status: str
    version: str
    llm_provider: str


@app.get("/health", response_model=Health)
async def health() -> Health:
    """Liveness probe. Reads config so a misconfigured container fails visibly."""
    settings = get_settings()
    return Health(status="ok", version=app.version, llm_provider=settings.llm_provider)
