"""
backend/routers/mixtape.py
---------------------------
POST /mixtape/create — merge uploaded tracks into a single audio file.

Security fixes applied (Day 3)
-------------------------------
1. validate_session_id() ensures session_id is a UUID4, blocking path traversal
   like "../../etc" that would escape the storage directory.
2. All audio loading is wrapped in try/except to catch pydub.CouldntDecodeError
   when a file is not actually valid audio (e.g. renamed text file).

Flow:
    1. Validate session_id format (UUID4)
    2. Read tracks from storage/{session_id}/raw/ in requested order
    3. Call audio_engine.merge_tracks() — the core logic
    4. Save merged audio + boundaries.json to storage/{session_id}/
    5. Return download URL + boundary data

Teaching note: notice how thin this is. The crossfade math, normalization,
and boundary tracking all happen inside audio_engine.py — this router just
wires HTTP request → service → HTTP response.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydub.exceptions import CouldntDecodeError

from backend.core.config import settings
from backend.core.security import validate_session_id
from backend.schemas.models import MixtapeRequest, MixtapeResponse, TrackBoundaryModel
from backend.services import audio_engine

router = APIRouter(prefix="/mixtape", tags=["mixtape"])


@router.post("/create", response_model=MixtapeResponse)
def create_mixtape(req: MixtapeRequest) -> MixtapeResponse:
    """
    Merge uploaded audio files into a single mixtape.

    - Validates session_id is a UUID4 (security).
    - Reads files from storage/{session_id}/raw/ in the requested order.
    - Applies optional crossfade and RMS normalization.
    - Handles corrupt/non-audio files with a clear 422 error.
    - Saves merged.mp3 and boundaries.json to storage/{session_id}/.
    - Returns a download URL and track boundary data.
    """
    # Security: reject any non-UUID4 session_id before using it in a Path
    validate_session_id(req.session_id)

    session_dir = settings.STORAGE_PATH / req.session_id
    raw_dir = session_dir / "raw"

    if not raw_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Session '{req.session_id}' not found. Upload files first.",
        )

    # Resolve file order: requested order or all files sorted alphabetically
    if req.order:
        paths = []
        for fname in req.order:
            # Sanitize each filename in the order list too
            safe_name = Path(fname).name
            p = raw_dir / safe_name
            if not p.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"File '{safe_name}' not found in session '{req.session_id}'.",
                )
            paths.append(p)
        names = [Path(fname).stem for fname in req.order]
    else:
        # Sort alphabetically as a sensible default
        paths = sorted(
            [p for p in raw_dir.iterdir() if p.is_file()],
            key=lambda p: p.name,
        )
        names = [p.stem for p in paths]

    if not paths:
        raise HTTPException(
            status_code=400,
            detail="No audio files found in session.",
        )

    # Load audio files — catch corrupt/non-audio files gracefully
    try:
        tracks = audio_engine.load_tracks(paths)
    except CouldntDecodeError as e:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Could not decode one or more audio files. "
                f"Make sure all uploaded files are valid audio. "
                f"ffmpeg error: {e}"
            ),
        )

    # Merge — all the real work happens inside audio_engine
    merged, boundaries = audio_engine.merge_tracks(
        tracks=tracks,
        names=names,
        crossfade_ms=req.crossfade_ms,
        normalize=req.normalize,
    )

    # Persist merged audio and boundaries
    merged_path = session_dir / "merged.mp3"
    audio_engine.export_audio(merged, merged_path, fmt="mp3")

    boundaries_path = session_dir / "boundaries.json"
    audio_engine.save_boundaries(boundaries, boundaries_path)

    return MixtapeResponse(
        session_id=req.session_id,
        merged_audio_url=f"/storage/{req.session_id}/merged.mp3",
        duration_ms=len(merged),
        boundaries=[
            TrackBoundaryModel(name=b.name, start_ms=b.start_ms, end_ms=b.end_ms)
            for b in boundaries
        ],
    )
