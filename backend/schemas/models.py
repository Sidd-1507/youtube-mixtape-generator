"""
backend/schemas/models.py
--------------------------
Pydantic v2 request/response models for all API endpoints.
These are the contracts between the API layer and its consumers (Streamlit, tests, curl).

Teaching notes
--------------
Pydantic models serve two jobs here:
  1. Request validation — FastAPI parses and validates incoming JSON automatically
  2. Response serialization — converts Python dataclasses to JSON with type safety

Keep these thin: no business logic, no service imports. Just data shapes.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    """Returned after POST /upload — client must store session_id for all subsequent calls."""
    session_id: str
    files: list[str]        # filenames as saved on disk (preserves original names)
    count: int


# ---------------------------------------------------------------------------
# Mixtape endpoint
# ---------------------------------------------------------------------------

class MixtapeRequest(BaseModel):
    """
    Body for POST /mixtape/create.

    `order` is a list of filenames (not full paths) in desired playback order.
    If order is empty or omitted, tracks are merged in upload order.
    """
    session_id: str
    order: list[str] = Field(
        default=[],
        description="Filenames in desired playback order. Empty = use upload order.",
    )
    crossfade_ms: int = Field(
        default=0,
        ge=0,
        le=10_000,
        description="Crossfade duration between tracks in milliseconds (0–10000).",
    )
    normalize: bool = Field(
        default=True,
        description="If true, RMS-normalize each track to -14 dBFS before merging.",
    )


class TrackBoundaryModel(BaseModel):
    """A single track's position in the merged audio."""
    name: str
    start_ms: int
    end_ms: int


class MixtapeResponse(BaseModel):
    """Returned after POST /mixtape/create."""
    session_id: str
    merged_audio_url: str           # relative URL to download merged audio
    duration_ms: int                # total merged audio length
    boundaries: list[TrackBoundaryModel]


# ---------------------------------------------------------------------------
# Description endpoint
# ---------------------------------------------------------------------------

class DescriptionRequest(BaseModel):
    session_id: str
    header: str | None = "🎵 Mixtape Tracklist\n"
    footer: str | None = "\n\n#mixtape #music"


class DescriptionResponse(BaseModel):
    session_id: str
    description: str


# ---------------------------------------------------------------------------
# Video endpoint
# ---------------------------------------------------------------------------

class VideoResponse(BaseModel):
    """Returned after POST /video/create."""
    session_id: str
    video_url: str                  # relative URL to download the .mp4
