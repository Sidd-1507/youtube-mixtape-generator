"""
tests/test_audio_engine.py
---------------------------
Unit tests for backend/services/audio_engine.py

These tests run with ZERO API, ZERO FastAPI, ZERO network.
All I/O uses pytest's tmp_path fixture for isolated temporary directories.

Teaching note: this is what "UI-agnostic core logic" means in practice —
you can test the entire audio merge pipeline without running a server.

Run with:
    uv run pytest tests/test_audio_engine.py -v
"""

from pathlib import Path
import shutil
import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from backend.services.audio_engine import (
    TrackBoundary,
    export_audio,
    load_boundaries,
    load_tracks,
    merge_tracks,
    normalize_track,
    save_boundaries,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic audio (no real mp3 files needed)
# ---------------------------------------------------------------------------

def make_sine_track(duration_ms: int, frequency: float = 440.0) -> AudioSegment:
    """Create a synthetic sine wave AudioSegment of exact duration."""
    return Sine(frequency).to_audio_segment(duration=duration_ms)


# ---------------------------------------------------------------------------
# normalize_track
# ---------------------------------------------------------------------------

class TestNormalizeTrack:
    def test_returns_audio_segment(self):
        seg = make_sine_track(1_000)
        result = normalize_track(seg)
        assert isinstance(result, AudioSegment)

    def test_normalized_dbfs_is_close_to_target(self):
        # Build a quiet track at ~-30 dBFS
        seg = make_sine_track(1_000)
        seg = seg.apply_gain(-20)
        result = normalize_track(seg, target_dbfs=-14.0)
        # After normalization, dBFS should be within ±1 dB of target
        assert abs(result.dBFS - (-14.0)) < 1.0

    def test_duration_preserved(self):
        seg = make_sine_track(3_000)
        result = normalize_track(seg)
        assert len(result) == 3_000


# ---------------------------------------------------------------------------
# merge_tracks — the critical test
# ---------------------------------------------------------------------------

class TestMergeTracks:
    """
    Key invariant to test:
        merged_duration = sum(track_durations) - crossfade_ms * (num_tracks - 1)

    And boundary math:
        track[0].start_ms == 0
        track[i].start_ms == previous_end_before_append - crossfade_ms
    """

    def test_single_track_no_crossfade(self):
        track = make_sine_track(10_000)
        merged, boundaries = merge_tracks([track], ["TrackA"], crossfade_ms=0)
        assert len(merged) == 10_000
        assert len(boundaries) == 1
        assert boundaries[0].start_ms == 0
        assert boundaries[0].end_ms == 10_000
        assert boundaries[0].name == "TrackA"

    def test_two_tracks_no_crossfade(self):
        a = make_sine_track(10_000)
        b = make_sine_track(8_000)
        merged, boundaries = merge_tracks([a, b], ["A", "B"], crossfade_ms=0)

        assert len(merged) == pytest.approx(18_000, abs=10)
        assert boundaries[0].start_ms == 0
        assert boundaries[1].start_ms == pytest.approx(10_000, abs=10)

    def test_two_tracks_with_crossfade(self):
        """
        A=10,000ms + B=8,000ms with crossfade=2,000ms:
            merged = 10,000 + 8,000 - 2,000 = 16,000ms
            B.start_ms = 10,000 - 2,000 = 8,000ms
        """
        a = make_sine_track(10_000)
        b = make_sine_track(8_000)
        crossfade = 2_000

        merged, boundaries = merge_tracks([a, b], ["A", "B"], crossfade_ms=crossfade)

        expected_duration = 10_000 + 8_000 - crossfade
        assert len(merged) == pytest.approx(expected_duration, abs=50)

        assert boundaries[0].start_ms == 0
        assert boundaries[1].start_ms == pytest.approx(10_000 - crossfade, abs=50)

    def test_three_tracks_crossfade_boundary_math(self):
        """
        A=6,000ms + B=7,000ms + C=5,000ms, crossfade=1,000ms:
            After A+B: 6,000 + 7,000 - 1,000 = 12,000ms
                B.start = 6,000 - 1,000 = 5,000ms
            After +C:  12,000 + 5,000 - 1,000 = 16,000ms
                C.start = 12,000 - 1,000 = 11,000ms
        """
        a = make_sine_track(6_000)
        b = make_sine_track(7_000)
        c = make_sine_track(5_000)
        crossfade = 1_000

        merged, boundaries = merge_tracks(
            [a, b, c], ["A", "B", "C"], crossfade_ms=crossfade, normalize=False
        )

        expected_total = 6_000 + 7_000 + 5_000 - 2 * crossfade  # = 16,000
        assert len(merged) == pytest.approx(expected_total, abs=50)

        assert boundaries[0].start_ms == 0
        assert boundaries[1].start_ms == pytest.approx(6_000 - crossfade, abs=50)  # 5,000
        assert boundaries[2].start_ms == pytest.approx(12_000 - crossfade, abs=50) # 11,000

    def test_mismatched_tracks_names_raises(self):
        tracks = [make_sine_track(5_000), make_sine_track(5_000)]
        with pytest.raises(ValueError, match="same length"):
            merge_tracks(tracks, ["OnlyOneName"], crossfade_ms=0)

    def test_empty_tracks_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            merge_tracks([], [], crossfade_ms=0)

    def test_crossfade_clamped_if_too_large(self):
        """Crossfade > track duration should be clamped, not crash."""
        a = make_sine_track(2_000)
        b = make_sine_track(2_000)
        # Request crossfade larger than the track — should be clamped
        merged, boundaries = merge_tracks([a, b], ["A", "B"], crossfade_ms=5_000)
        assert len(merged) > 0  # didn't crash


# ---------------------------------------------------------------------------
# export_audio + load_tracks round-trip
# ---------------------------------------------------------------------------


_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _FFMPEG_AVAILABLE, reason="ffmpeg not installed — MP3 encode/decode requires ffmpeg")
class TestExportLoadRoundTrip:
    def test_export_creates_file(self, tmp_path: Path):
        seg = make_sine_track(3_000)
        out = tmp_path / "test.mp3"
        result = export_audio(seg, out, fmt="mp3")
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0

    def test_load_tracks_returns_segments(self, tmp_path: Path):
        # Export two files, then load them back
        seg1 = make_sine_track(2_000, frequency=440)
        seg2 = make_sine_track(3_000, frequency=880)
        p1 = tmp_path / "a.mp3"
        p2 = tmp_path / "b.mp3"
        export_audio(seg1, p1, fmt="mp3")
        export_audio(seg2, p2, fmt="mp3")

        loaded = load_tracks([p1, p2])
        assert len(loaded) == 2
        assert isinstance(loaded[0], AudioSegment)
        assert isinstance(loaded[1], AudioSegment)


# ---------------------------------------------------------------------------
# save/load boundaries round-trip
# ---------------------------------------------------------------------------

class TestBoundariesRoundTrip:
    def test_save_and_load(self, tmp_path: Path):
        original = [
            TrackBoundary(name="Alpha", start_ms=0, end_ms=180_000),
            TrackBoundary(name="Beta", start_ms=177_000, end_ms=387_000),
            TrackBoundary(name="Gamma", start_ms=384_000, end_ms=579_000),
        ]
        path = tmp_path / "boundaries.json"
        save_boundaries(original, path)
        loaded = load_boundaries(path)

        assert len(loaded) == 3
        assert loaded[0].name == "Alpha"
        assert loaded[1].start_ms == 177_000
        assert loaded[2].end_ms == 579_000
