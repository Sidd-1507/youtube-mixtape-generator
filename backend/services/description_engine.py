"""
backend/services/description_engine.py
----------------------------------------
UI-AGNOSTIC description generation.
NO imports from fastapi, streamlit, pydub, or any other heavy library.
Pure Python string logic — trivially testable with no I/O.

Teaching notes
--------------
This module has exactly two jobs:
  1. Convert milliseconds → human-readable timestamp string ("3:45", "1:03:45")
  2. Format a list of TrackBoundary objects into a YouTube description

The timestamp logic must handle:
  - Sub-hour: "3:45"  (M:SS — no leading zero on minutes)
  - Over hour: "1:03:45"  (H:MM:SS — no leading zero on hours)
  - Edge cases: 0ms → "0:00", 3,599,999ms → "59:59", 3,600,000ms → "1:00:00"
"""

from __future__ import annotations

from backend.services.audio_engine import TrackBoundary


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------

def format_timestamp(ms: int) -> str:
    """
    Convert a duration in milliseconds to a YouTube-style timestamp string.

    Rules:
        < 1 hour  →  "M:SS"   (e.g. "3:45", "59:07")
        >= 1 hour →  "H:MM:SS" (e.g. "1:03:45", "2:00:00")

    Args:
        ms: Non-negative integer milliseconds.

    Returns:
        Formatted string suitable for a YouTube description timestamp.

    Examples:
        >>> format_timestamp(0)
        '0:00'
        >>> format_timestamp(225_000)   # 3 min 45 sec
        '3:45'
        >>> format_timestamp(3_705_000) # 1 hr 1 min 45 sec
        '1:01:45'
    """
    if ms < 0:
        ms = 0

    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


# ---------------------------------------------------------------------------
# Description generation
# ---------------------------------------------------------------------------

DEFAULT_HEADER = "🎵 Mixtape Tracklist\n"
DEFAULT_FOOTER = "\n\n#mixtape #music"


def generate_description(
    boundaries: list[TrackBoundary],
    header: str | None = DEFAULT_HEADER,
    footer: str | None = DEFAULT_FOOTER,
) -> str:
    """
    Generate a YouTube-ready description with clickable timestamps.

    Output format:
        🎵 Mixtape Tracklist

        0:00 Track One
        3:45 Track Two
        7:30 Track Three

        #mixtape #music

    Args:
        boundaries: List of TrackBoundary from audio_engine.merge_tracks().
                    Uses start_ms for each timestamp.
        header:     Optional prefix text. Pass None or "" to omit.
        footer:     Optional suffix text. Pass None or "" to omit.

    Returns:
        A ready-to-paste YouTube description string.
    """
    lines: list[str] = []

    if header:
        lines.append(header)

    for boundary in boundaries:
        timestamp = format_timestamp(boundary.start_ms)
        lines.append(f"{timestamp} {boundary.name}")

    if footer:
        lines.append(footer)

    return "\n".join(lines)
