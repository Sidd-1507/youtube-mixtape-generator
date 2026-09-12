"""
backend/main.py
----------------
FastAPI application entrypoint.

Architecture overview:
    main.py         — mounts all routers, adds middleware, serves static files
    routers/        — HTTP translation layer (thin wrappers)
    services/       — core business logic (UI-agnostic)
    core/config.py  — settings from .env
    storage/        — generated session files (gitignored)

Run with:
    uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.routers import description, mixtape, upload, video

app = FastAPI(
    title="YouTube Mixtape Generator API",
    description=(
        "API for merging audio tracks, generating YouTube descriptions with timestamps, "
        "and creating MP4 videos with a static background image."
    ),
    version="0.1.0",
    docs_url="/docs",       # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow Streamlit (different port) to call this API
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # restrict to ["http://localhost:8501"] in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(upload.router)
app.include_router(mixtape.router)
app.include_router(description.router)
app.include_router(video.router)

# ---------------------------------------------------------------------------
# Static file serving — lets Streamlit download merged.mp3 and mixtape.mp4
# via /storage/{session_id}/merged.mp3 etc.
# ---------------------------------------------------------------------------
app.mount(
    "/storage",
    StaticFiles(directory=str(settings.STORAGE_PATH)),
    name="storage",
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health_check() -> dict:
    """Quick liveness check — returns 200 if the API is running."""
    return {
        "status": "ok",
        "storage": str(settings.STORAGE_PATH),
    }
