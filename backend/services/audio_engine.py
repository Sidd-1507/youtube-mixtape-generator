"""
backend/services/audio_engine.py
---------------------------------
UI-AGNOSTIC core audio logic.
NO imports from fastapi, streamlit, or any web framework.
Inputs and outputs are plain Python types: Path, list, dataclass.

Teaching notes
--------------
Crossfade boundary math (the subtle part):
    When pydub appends with crossfade=N ms, it OVERLAPS the last N ms of
    the current segment with the first N ms of the next segment.
    So the total duration SHRINKS by N ms for each crossfade applied.

    Example — 3 tracks:
        A = 180,000 ms
        B = 210,000 ms
        C = 195,000 ms
        crossfade = 3,000 ms

    After A + B (crossfade 3s):
        merged = 180,000 + 210,000 - 3,000 = 387,000 ms
        B.start_ms = 180,000 - 3,000 = 177,000  ← listener hears B here
        B.end_ms   = 177,000 + 210,000 = 387,000

    After (A+B) + C (crossfade 3s):
        merged = 387,000 + 195,000 - 3,000 = 579,000 ms
        C.start_ms = 387,000 - 3,000 = 384,000
        C.end_ms   = 384,000 + 195,000 = 579,000

    If you used naive cumulative sum (A.dur + B.dur + C.dur), Track 10
    on a 10-track mixtape would have timestamps drifted by 27 seconds.
    GET THIS RIGHT ON DAY 1.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

from pydub import AudioSegment
from pydub import effects as pydub_effects


@dataclass
class TrackBoundary:
    """Represents one track's position inside the final merged audio."""
    name: str       # display name (usually the filename stem)
    start_ms: int   # millisecond offset where this track becomes audible
    end_ms: int     # millisecond offset where this track ends


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_tracks(paths: list[Path]) -> list[AudioSegment]:
    """
    Load audio files from disk into pydub AudioSegments.

    pydub supports: mp3, wav, ogg, flac, aac, m4a (when ffmpeg is installed).
    Returns a list of AudioSegments in the same order as `paths`.
    """
    segments: list[AudioSegment] = []
    for p in paths:
        seg = AudioSegment.from_file(str(p))
        segments.append(seg)
    return segments


_TARGET_DBFS = -14.0  # Spotify/YouTube streaming loudness standard


def normalize_track(segment: AudioSegment, target_dbfs: float = _TARGET_DBFS) -> AudioSegment:
    """
    Normalize a track to a target RMS loudness level using gain adjustment.

    WHY NOT pydub's normalize()?
        normalize() scales based on the PEAK sample — a quiet track with one
        loud transient will peak-normalize fine but still SOUND quiet compared
        to other tracks. Cross-track consistency is not guaranteed.

    THIS approach uses RMS (average energy via segment.dBFS) and shifts the
    entire track's gain so its average loudness matches target_dbfs.
    This is what Spotify and YouTube use (both target ~-14 LUFS / -14 dBFS).

    EDGE CASES HANDLED:
        1. Silence (dBFS = -inf): apply_gain(+inf) would corrupt the audio
           to NaN samples. We detect this and return silence unchanged.
        2. Gain clamping: we cap the change at ±60 dB to prevent extreme
           adjustments on near-silent tracks (e.g. fade-ins).

    Args:
        segment:     Input AudioSegment.
        target_dbfs: Target RMS loudness in dBFS (default: -14.0).

    Returns:
        Gain-adjusted AudioSegment, or original if silent.
    """
    if math.isinf(segment.dBFS):
        # Track is complete silence — returning unchanged is the only safe option.
        # apply_gain(float('inf')) would produce NaN samples and corrupt the audio.
        return segment

    change_in_dbfs = target_dbfs - segment.dBFS

    # Clamp to ±60 dB to prevent extreme amplification or attenuation.
    # Real tracks should never need more than ±20 dB; this is a safety guard.
    change_in_dbfs = max(-60.0, min(60.0, change_in_dbfs))

    return segment.apply_gain(change_in_dbfs)


def merge_tracks(
    tracks: list[AudioSegment],
    names: list[str],
    crossfade_ms: int = 0,
    normalize: bool = True,
) -> tuple[AudioSegment, list[TrackBoundary]]:
    """
    Merge a list of AudioSegments into one continuous AudioSegment,
    computing correct TrackBoundary offsets accounting for crossfade overlap.

    Args:
        tracks:       List of AudioSegments (same order as desired playback).
        names:        Display names for each track (same length as tracks).
        crossfade_ms: Overlap duration between consecutive tracks (ms).
        normalize:    If True, normalize each track before merging.

    Returns:
        (merged_segment, boundaries)
        - merged_segment: single AudioSegment containing the full mixtape.
        - boundaries: list[TrackBoundary] with correct start_ms/end_ms for
          each track — used by description_engine and timestamp display.

    Raises:
        ValueError: if tracks and names have different lengths.
    """
    if len(tracks) != len(names):
        raise ValueError(
            f"tracks ({len(tracks)}) and names ({len(names)}) must have the same length"
        )
    if not tracks:
        raise ValueError("tracks list must not be empty")

    # Clamp crossfade to avoid exceeding shortest track
    min_duration = min(len(t) for t in tracks)
    if crossfade_ms > min_duration:
        crossfade_ms = min_duration // 2  # safe fallback

    if normalize:
        tracks = [normalize_track(t) for t in tracks]

    boundaries: list[TrackBoundary] = []
    merged = tracks[0]

    # First track always starts at 0
    boundaries.append(TrackBoundary(
        name=names[0],
        start_ms=0,
        end_ms=len(tracks[0]),
    ))

    for i, track in enumerate(tracks[1:], start=1):
        # current_end_ms is the length of `merged` BEFORE we append `track`
        current_end_ms = len(merged)

        # The listener hears this track start at (current_end - crossfade_ms)
        # because crossfade overlaps the tail of merged with the head of track.
        track_start_ms = current_end_ms - crossfade_ms

        # Append with crossfade — merged grows by (len(track) - crossfade_ms)
        merged = merged.append(track, crossfade=crossfade_ms)

        track_end_ms = track_start_ms + len(track)

        boundaries.append(TrackBoundary(
            name=names[i],
            start_ms=track_start_ms,
            end_ms=track_end_ms,
        ))

    return merged, boundaries


def export_audio(
    segment: AudioSegment,
    out_path: Path,
    fmt: str = "mp3",
    bitrate: str = "192k",
) -> Path:
    """
    Export an AudioSegment to disk.

    Args:
        segment:  The AudioSegment to export.
        out_path: Destination file path (extension should match fmt).
        fmt:      Output format ('mp3', 'wav', 'ogg', etc.).
        bitrate:  Audio bitrate (relevant for lossy formats like mp3).

    Returns:
        The out_path, for easy chaining.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    segment.export(str(out_path), format=fmt, bitrate=bitrate)
    return out_path


def save_boundaries(boundaries: list[TrackBoundary], out_path: Path) -> Path:
    """Persist boundaries as JSON so the description/video routers can read them."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(b) for b in boundaries]
    out_path.write_text(json.dumps(data, indent=2))
    return out_path


def load_boundaries(json_path: Path) -> list[TrackBoundary]:
    """Load TrackBoundary list from a JSON file saved by save_boundaries()."""
    data = json.loads(json_path.read_text())
    return [TrackBoundary(**item) for item in data]
