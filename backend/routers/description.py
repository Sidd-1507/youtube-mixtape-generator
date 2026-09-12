"""
backend/routers/description.py
--------------------------------
POST /description/generate — generate YouTube description from saved boundaries.

Security fixes applied (Day 3)
-------------------------------
validate_session_id() ensures the session_id is a UUID4 before using it in a
file path, preventing path traversal attacks.
"""

from fastapi import APIRouter, HTTPException

from backend.core.config import settings
from backend.core.security import validate_session_id
from backend.schemas.models import DescriptionRequest, DescriptionResponse
from backend.services import audio_engine, description_engine

router = APIRouter(prefix="/description", tags=["description"])


@router.post("/generate", response_model=DescriptionResponse)
def generate_description(req: DescriptionRequest) -> DescriptionResponse:
    """
    Generate a YouTube-ready timestamped description for a completed mixtape.

    Reads track boundaries saved by /mixtape/create.
    Returns a description string with timestamps like:
        🎵 Mixtape Tracklist
        0:00 Track One
        3:45 Track Two
        #mixtape #music

    Requires /mixtape/create to have been called first.
    """
    validate_session_id(req.session_id)

    boundaries_path = settings.STORAGE_PATH / req.session_id / "boundaries.json"

    if not boundaries_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"No boundaries found for session '{req.session_id}'. "
                "Run POST /mixtape/create first."
            ),
        )

    try:
        boundaries = audio_engine.load_boundaries(boundaries_path)
    except (ValueError, Exception) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"boundaries.json is corrupted or unreadable: {exc}",
        )

    description = description_engine.generate_description(
        boundaries=boundaries,
        header=req.header,
        footer=req.footer,
    )

    return DescriptionResponse(session_id=req.session_id, description=description)
