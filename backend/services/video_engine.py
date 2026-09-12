"""
backend/services/video_engine.py
----------------------------------
UI-AGNOSTIC video generation using ffmpeg via subprocess.
NO imports from fastapi, streamlit, moviepy, or any web framework.

Why ffmpeg subprocess instead of moviepy?
-----------------------------------------
For "one static image + audio → .mp4":
  - moviepy loads the image, creates a clip, renders every frame → slow
  - ffmpeg handles this in one native C call: `-loop 1 -i image -t <dur>`
  - For a 20-minute mixtape, ffmpeg takes ~10s vs moviepy ~60-90s
  - ffmpeg is already a system dependency (pydub needs it too)
  - Easier to debug: stderr is plain ffmpeg output

Duration bug fix
-----------------
Using `-shortest` with `-framerate 1 -loop 1` causes ffmpeg to produce
extra frames during encoder flush, making the video 2–3x longer than the
audio. Fix: probe the audio duration with ffprobe first, then pass `-t`
explicitly so ffmpeg stops encoding at exactly the audio end.

The exact command we run:
    ffmpeg -y
      -loop 1 -framerate 2 -i background.jpg  # loop static image at 2fps
      -i mixtape.mp3                           # audio input
      -t <audio_duration_seconds>              # explicit duration cap
      -c:v libx264 -tune stillimage            # fast video codec for static content
      -c:a aac -b:a 192k                       # audio codec + bitrate
      -pix_fmt yuv420p                         # required for browser/YouTube compat
      -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" # force even dimensions (libx264 req)
      -movflags +faststart                     # metadata at file start (web streaming)
      output.mp4
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def check_ffmpeg() -> bool:
    """
    Return True if ffmpeg is available on PATH, False otherwise.
    Call this at startup to give a clear error message.
    """
    return shutil.which("ffmpeg") is not None


def _probe_audio_duration(audio_path: Path) -> float:
    """
    Use ffprobe to get the exact duration of an audio file in seconds.
    More accurate than relying on pydub's len() which includes encoding lag.
    Falls back to 0.0 if ffprobe is not available.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    result = subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json",
         "-show_format", str(audio_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return 0.0
    try:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 0.0


def image_audio_to_video(
    image_path: Path,
    audio_path: Path,
    out_path: Path,
    video_bitrate: str = "2M",
    audio_bitrate: str = "192k",
) -> Path:
    """
    Combine a static background image + audio file into an MP4 video.

    The image is looped (no animation) for the full duration of the audio.
    This is exactly what YouTube "visualizer" / "lyric video" style uploads use.

    Args:
        image_path:    Path to a JPEG or PNG background image.
        audio_path:    Path to the merged audio file (mp3, wav, etc.).
        out_path:      Destination .mp4 file path.
        video_bitrate: libx264 bitrate (default "2M" = 2 Mbit/s, enough for static).
        audio_bitrate: AAC bitrate (default "192k").

    Returns:
        out_path on success.

    Raises:
        FileNotFoundError: if image_path or audio_path do not exist.
        RuntimeError:      if ffmpeg returns a non-zero exit code.
        EnvironmentError:  if ffmpeg is not installed.
    """
    if not check_ffmpeg():
        raise EnvironmentError(
            "ffmpeg not found on PATH. Install with: brew install ffmpeg (macOS) "
            "or: sudo apt install ffmpeg (Ubuntu/Debian)"
        )

    if not image_path.exists():
        raise FileNotFoundError(f"Background image not found: {image_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Probe the audio duration explicitly.
    # WHY: using -shortest with -framerate 1 causes ffmpeg to add extra frames
    # during encoder flush, making the video longer than the audio. Using -t
    # with the exact audio duration prevents this entirely.
    audio_duration = _probe_audio_duration(audio_path)

    cmd = [
        "ffmpeg",
        "-y",                                    # overwrite output without asking
        "-loop", "1",                            # loop the image indefinitely
        "-framerate", "2",                       # 2fps for static image — fast encode, compatible
        "-i", str(image_path),                   # input 0: image
        "-i", str(audio_path),                   # input 1: audio
    ]

    # If we have a valid audio duration, cap the video exactly at that length.
    # Fall back to -shortest if ffprobe is not available.
    if audio_duration > 0:
        cmd += ["-t", str(audio_duration)]
    else:
        cmd += ["-shortest"]

    cmd += [
        "-c:v", "libx264",                       # H.264 video codec
        "-tune", "stillimage",                   # optimise encoder for static content
        "-b:v", video_bitrate,                   # video bitrate
        "-c:a", "aac",                           # AAC audio codec
        "-b:a", audio_bitrate,                   # audio bitrate
        "-pix_fmt", "yuv420p",                   # required for browser/YouTube compat
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # force even dimensions
        "-movflags", "+faststart",               # metadata at file start (web streaming)
        str(out_path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed with exit code {result.returncode}.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stderr:\n{result.stderr}"
        )

    return out_path
