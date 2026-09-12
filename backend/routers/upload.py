"""
backend/routers/upload.py
--------------------------
POST /upload — receive multiple audio files, create session, save to disk.

Security fixes applied (Day 3)
-------------------------------
1. safe_filename() strips directory components from uploaded filenames.
   Without this, a filename like "../../../etc/passwd" would escape
   the storage directory when joined with Path().

2. Extension validation only allows known audio formats.

Teaching note: the router's ONLY job is HTTP translation:
    HTTP multipart/form-data  →  list[Path]  →  persist to disk
    Results dict              →  JSON response

No business logic here. If you find yourself doing audio processing in a router,
move it to a service.
"""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.core.config import settings
from backend.core.security import safe_filename
from backend.schemas.models import UploadResponse

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}


@router.post("", response_model=UploadResponse)
async def upload_files(files: list[UploadFile] = File(...)) -> UploadResponse:
    """
    Upload one or more audio files and create a new session.

    - Generates a UUID4 session_id for isolation.
    - Sanitizes filenames to prevent path traversal attacks.
    - Saves files to storage/{session_id}/raw/.
    - Returns session_id + saved filenames.

    The session_id must be passed to all subsequent endpoints.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    # Validate each file BEFORE creating any folders or saving anything.
    # If any file is bad, reject the entire batch with a clear error.
    sanitized: list[tuple[UploadFile, str]] = []
    for f in files:
        # safe_filename raises 400 if the name is empty or has path components
        name = safe_filename(f.filename)

        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type '{suffix}' for '{name}'. "
                    f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
                ),
            )
        sanitized.append((f, name))

    # All files valid — now create the session and save
    session_id = str(uuid.uuid4())
    raw_dir = settings.STORAGE_PATH / session_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    for f, name in sanitized:
        dest = raw_dir / name
        with dest.open("wb") as buf:
            shutil.copyfileobj(f.file, buf)
        saved.append(name)

    return UploadResponse(session_id=session_id, files=saved, count=len(saved))
