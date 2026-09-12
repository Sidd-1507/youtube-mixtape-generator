"""
backend/routers/video.py
-------------------------
POST /video/create — combine a background image + merged audio into .mp4

Security fixes applied (Day 3)
-------------------------------
1. validate_session_id() — prevents path traversal via session_id
2. safe_filename() on image filename — prevents path traversal in image name
3. Explicit check that merged.mp3 exists before saving the image, so we
   don't write to disk if the prerequisite is missing (fail-fast).

The client sends:
  - session_id (form field)
  - image file (UploadFile)

The router:
  1. Validates session_id (UUID4)
  2. Verifies merged.mp3 exists (created by /mixtape/create)
  3. Saves the image to storage/{session_id}/background.{ext}
  4. Calls video_engine.image_audio_to_video()
  5. Returns a download URL for the .mp4
"""

import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.core.config import settings
from backend.core.security import validate_session_id
from backend.schemas.models import VideoResponse
from backend.services import video_engine

router = APIRouter(prefix="/video", tags=["video"])

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@router.post("/create", response_model=VideoResponse)
def create_video(
    session_id: str = Form(...),
    image: UploadFile = File(...),
) -> VideoResponse:
    """
    Create an MP4 video from the session's merged audio + a background image.

    Requires /mixtape/create to have been run first (merged.mp3 must exist).
    Accepts JPEG or PNG background images.
    ffmpeg must be installed (brew install ffmpeg on macOS).
    """
    validate_session_id(session_id)

    session_dir = settings.STORAGE_PATH / session_id
    merged_audio = session_dir / "merged.mp3"

    if not merged_audio.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Merged audio not found for session '{session_id}'. "
                "Run POST /mixtape/create first."
            ),
        )

    # Validate image type before writing anything to disk (fail-fast)
    image_suffix = Path(image.filename or "").suffix.lower()
    if image_suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type '{image_suffix}'. Use JPEG or PNG.",
        )

    # Save the image
    image_path = session_dir / f"background{image_suffix}"
    with image_path.open("wb") as buf:
        shutil.copyfileobj(image.file, buf)

    # Generate video — ffmpeg runs here, may take 10-60 seconds
    out_path = session_dir / "mixtape.mp4"
    try:
        video_engine.image_audio_to_video(
            image_path=image_path,
            audio_path=merged_audio,
            out_path=out_path,
        )
    except EnvironmentError as e:
        # ffmpeg not installed
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        # ffmpeg ran but the encode failed
        raise HTTPException(status_code=500, detail=str(e))

    return VideoResponse(
        session_id=session_id,
        video_url=f"/storage/{session_id}/mixtape.mp4",
    )
