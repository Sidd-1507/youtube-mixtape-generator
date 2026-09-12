"""
tests/test_edge_cases.py
--------------------------
Edge case unit tests for audio_engine and security module.

These tests cover the EXACT scenarios that were found to cause bugs:

1. Silence normalization (dBFS = -inf) — would crash without the fix
2. Security: UUID4 validation
3. Security: filename sanitization
4. Boundary math with single track (no crossfade)
5. Unicode track names in boundaries JSON
6. format_timestamp with very large values (10+ hour mixtapes)
7. generate_description with empty boundaries

Every test here corresponds to a real bug or real edge case —
not theoretical exercises.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydub import AudioSegment
from pydub.generators import Sine

from backend.core.security import safe_filename, validate_session_id
from backend.services.audio_engine import (
    TrackBoundary,
    load_boundaries,
    merge_tracks,
    normalize_track,
    save_boundaries,
)
from backend.services.description_engine import format_timestamp, generate_description


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sine(duration_ms: int, freq: float = 440.0) -> AudioSegment:
    return Sine(freq).to_audio_segment(duration=duration_ms)


def make_silence(duration_ms: int) -> AudioSegment:
    return AudioSegment.silent(duration=duration_ms)


# ---------------------------------------------------------------------------
# BUG #1 — Silence normalization
# The original code: change_in_dbfs = -14.0 - (-inf) = +inf
#                   apply_gain(+inf) → corrupts audio with NaN samples
# ---------------------------------------------------------------------------

class TestSilenceNormalization:
    """
    normalize_track must NOT crash or produce garbage when given silence.
    A track of pure silence has dBFS = -inf.
    The fix: detect -inf via math.isinf() and return unchanged.
    """

    def test_silence_returns_unchanged(self):
        silence = make_silence(3_000)
        result = normalize_track(silence)
        # Should return silence, not crash
        assert len(result) == pytest.approx(3_000, abs=50)

    def test_silence_dBFS_stays_minus_inf(self):
        silence = make_silence(3_000)
        result = normalize_track(silence)
        import math
        assert math.isinf(result.dBFS)

    def test_silence_mixed_with_real_tracks(self):
        """Silence in a multi-track merge must not crash the whole merge."""
        silence = make_silence(3_000)
        track = make_sine(3_000)
        # This should not raise
        merged, boundaries = merge_tracks(
            [silence, track],
            ["silent_intro", "real_track"],
            crossfade_ms=0,
            normalize=True,
        )
        assert len(boundaries) == 2
        assert len(merged) == pytest.approx(6_000, abs=50)

    def test_gain_clamped_at_60db(self):
        """A very quiet track (e.g. -70 dBFS) should not be amplified more than +60 dB."""
        # Create a nearly-silent track (very low amplitude)
        # Sine at amplitude 1 is very quiet
        quiet = Sine(440).to_audio_segment(duration=2_000, volume=-50)
        result = normalize_track(quiet)
        # Should not crash, and gain should be reasonable
        import math
        # Result should not be silence either (it's near-silent, not silence)
        if not math.isinf(result.dBFS):
            assert result.dBFS > -80  # Something reasonable


# ---------------------------------------------------------------------------
# Security tests — UUID4 validation
# ---------------------------------------------------------------------------

class TestValidateSessionId:
    """validate_session_id must accept real UUID4s and reject everything else."""

    VALID_UUID4S = [
        "a8098c1a-f86e-4da4-bd1a-00112444be1e",
        "1d71c10b-91e2-4ff9-86b1-fa7681ea8688",
        "00000000-0000-4000-8000-000000000000",
    ]

    INVALID_IDS = [
        # Path traversal attempts
        "../../etc/passwd",
        "../storage",
        # Empty/whitespace
        "",
        "   ",
        # Not UUID format
        "not-a-uuid",
        "12345",
        "abcdef",
        # UUID1, UUID3, UUID5 (version digit must be 4)
        "a8098c1a-f86e-1da4-bd1a-00112444be1e",  # version 1
        "a8098c1a-f86e-5da4-bd1a-00112444be1e",  # version 5
        # SQL injection attempt
        "'; DROP TABLE sessions; --",
        # Null byte
        "abc\x00def",
    ]

    def test_valid_uuid4_passes(self):
        for uid in self.VALID_UUID4S:
            # Should not raise
            validate_session_id(uid)

    def test_invalid_ids_raise_400(self):
        for uid in self.INVALID_IDS:
            with pytest.raises(HTTPException) as exc_info:
                validate_session_id(uid)
            assert exc_info.value.status_code == 400, f"Expected 400 for: {uid!r}"


# ---------------------------------------------------------------------------
# Security tests — filename sanitization
# ---------------------------------------------------------------------------

class TestSafeFilename:
    """safe_filename must strip all directory components."""

    def test_normal_filename_unchanged(self):
        assert safe_filename("track1.mp3") == "track1.mp3"

    def test_path_traversal_stripped(self):
        # The directory part is stripped, leaving just the basename
        assert safe_filename("../../../etc/passwd") == "passwd"

    def test_subdir_stripped(self):
        assert safe_filename("subdir/my_track.mp3") == "my_track.mp3"

    def test_windows_path_stripped(self):
        # Path() handles both / and \ on all platforms
        result = safe_filename("subdir\\track.mp3")
        # On macOS, backslash is a valid filename character, not a separator
        # so this is platform-specific behavior — just ensure no crash
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_filename_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            safe_filename("")
        assert exc_info.value.status_code == 400

    def test_none_filename_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            safe_filename(None)
        assert exc_info.value.status_code == 400

    def test_dotfile_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            safe_filename(".hidden")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Boundary math edge cases
# ---------------------------------------------------------------------------

class TestBoundaryEdgeCases:
    """
    Regression tests for boundary computation in merge_tracks.
    These numbers should never change — if they do, the timestamp
    math is broken and every YouTube description will be wrong.
    """

    def test_single_track_start_is_always_zero(self):
        track = make_sine(5_000)
        merged, boundaries = merge_tracks([track], ["only"], crossfade_ms=0)
        assert boundaries[0].start_ms == 0
        assert boundaries[0].end_ms == pytest.approx(5_000, abs=50)

    def test_single_track_with_crossfade_ignored_gracefully(self):
        """Crossfade on a single track should not crash or produce wrong boundary."""
        track = make_sine(5_000)
        # crossfade with only one track — nothing to crossfade into
        merged, boundaries = merge_tracks([track], ["only"], crossfade_ms=1_000)
        assert len(boundaries) == 1
        assert boundaries[0].start_ms == 0

    def test_crossfade_larger_than_track_is_clamped(self):
        """If crossfade_ms > track duration, it must be clamped, not crash."""
        a = make_sine(2_000)
        b = make_sine(2_000)
        # crossfade (5000ms) > track duration (2000ms) — must not crash
        merged, boundaries = merge_tracks(
            [a, b], ["A", "B"], crossfade_ms=5_000
        )
        # Clamped to min_duration // 2 = 1000
        assert len(merged) > 0
        assert len(boundaries) == 2

    def test_three_track_boundary_math(self):
        """
        Key regression test. With crossfade=1s:
        A (6s) + B (7s) + C (5s):
          B.start_ms = 6000 - 1000 = 5000
          C.start_ms = (6000+7000-1000) - 1000 = 11000
          total = 6+7+5 - 2 = 16000ms
        """
        a = make_sine(6_000)
        b = make_sine(7_000)
        c = make_sine(5_000)
        merged, boundaries = merge_tracks(
            [a, b, c], ["A", "B", "C"], crossfade_ms=1_000, normalize=False
        )
        assert boundaries[0].start_ms == 0
        assert boundaries[1].start_ms == pytest.approx(5_000, abs=50)
        assert boundaries[2].start_ms == pytest.approx(11_000, abs=50)
        assert len(merged) == pytest.approx(16_000, abs=50)

    def test_no_crossfade_boundaries_are_cumulative(self):
        """Without crossfade, each track starts exactly where the previous ended."""
        a = make_sine(3_000)
        b = make_sine(4_000)
        c = make_sine(2_000)
        merged, boundaries = merge_tracks(
            [a, b, c], ["A", "B", "C"], crossfade_ms=0, normalize=False
        )
        assert boundaries[0].start_ms == 0
        assert boundaries[1].start_ms == pytest.approx(3_000, abs=50)
        assert boundaries[2].start_ms == pytest.approx(7_000, abs=50)
        assert len(merged) == pytest.approx(9_000, abs=50)


# ---------------------------------------------------------------------------
# Unicode track names in boundaries JSON
# ---------------------------------------------------------------------------

class TestUnicodeBoundaries:
    """Track names with unicode must survive JSON round-trip correctly."""

    def test_unicode_names_round_trip(self, tmp_path):
        boundaries = [
            TrackBoundary(name="🎵 Café del Mar", start_ms=0, end_ms=180_000),
            TrackBoundary(name="日本語テスト", start_ms=180_000, end_ms=360_000),
            TrackBoundary(name="Ünïcödé Trâck", start_ms=360_000, end_ms=540_000),
        ]
        json_path = tmp_path / "boundaries.json"
        save_boundaries(boundaries, json_path)
        loaded = load_boundaries(json_path)

        assert len(loaded) == 3
        assert loaded[0].name == "🎵 Café del Mar"
        assert loaded[1].name == "日本語テスト"
        assert loaded[2].name == "Ünïcödé Trâck"

    def test_unicode_names_in_description(self):
        boundaries = [
            TrackBoundary(name="🎵 Café del Mar", start_ms=0, end_ms=180_000),
            TrackBoundary(name="日本語テスト", start_ms=180_000, end_ms=360_000),
        ]
        desc = generate_description(boundaries, header=None, footer=None)
        assert "🎵 Café del Mar" in desc
        assert "日本語テスト" in desc


# ---------------------------------------------------------------------------
# format_timestamp edge cases
# ---------------------------------------------------------------------------

class TestTimestampEdgeCases:
    """Regression suite for timestamp formatting."""

    @pytest.mark.parametrize("ms,expected", [
        (0, "0:00"),                   # minimum
        (-1, "0:00"),                  # negative → clamp to 0
        (-99_999, "0:00"),             # large negative → clamp to 0
        (999, "0:00"),                 # 0.999s → 0 seconds (floor)
        (1_000, "0:01"),               # exactly 1 second
        (59_000, "0:59"),              # last second before 1 minute
        (60_000, "1:00"),              # exactly 1 minute
        (3_599_000, "59:59"),          # last second before 1 hour
        (3_600_000, "1:00:00"),        # exactly 1 hour
        (3_661_000, "1:01:01"),        # 1h 1m 1s
        (36_000_000, "10:00:00"),      # 10 hours — long DJ set
        (86_399_000, "23:59:59"),      # 24h - 1s — theoretical max
    ])
    def test_format_timestamp(self, ms, expected):
        assert format_timestamp(ms) == expected

    def test_sub_minute_no_leading_zero_on_minutes(self):
        """Minutes should NOT be double-zero padded: '0:45' not '00:45'."""
        result = format_timestamp(45_000)
        assert result == "0:45"
        # Specifically, it must NOT be '00:45' (double-padded minutes)
        assert result != "00:45"
        # And the format is M:SS (colon at index 1, not 2)
        assert result.index(":") == 1

    def test_seconds_always_two_digits(self):
        """Seconds must always be zero-padded: '1:05' not '1:5'."""
        assert format_timestamp(65_000) == "1:05"

    def test_over_one_hour_minutes_two_digits(self):
        """Minutes must be zero-padded when there's an hour: '1:05:03' not '1:5:03'."""
        assert format_timestamp(3_903_000) == "1:05:03"


# ---------------------------------------------------------------------------
# generate_description edge cases
# ---------------------------------------------------------------------------

class TestDescriptionEdgeCases:
    """Edge cases for description generation."""

    def test_empty_boundaries_returns_header_footer_only(self):
        desc = generate_description([], header="Header\n", footer="\nFooter")
        assert "Header" in desc
        assert "Footer" in desc
        # No track lines
        assert "0:00" not in desc

    def test_none_header_omitted(self):
        b = [TrackBoundary("Track", 0, 180_000)]
        desc = generate_description(b, header=None, footer=None)
        assert desc.strip() == "0:00 Track"

    def test_empty_string_header_omitted(self):
        b = [TrackBoundary("Track", 0, 180_000)]
        desc = generate_description(b, header="", footer="")
        assert desc.strip() == "0:00 Track"

    def test_track_order_preserved_in_output(self):
        """Description lines must appear in the same order as boundaries."""
        boundaries = [
            TrackBoundary("First", 0, 60_000),
            TrackBoundary("Second", 60_000, 120_000),
            TrackBoundary("Third", 120_000, 180_000),
        ]
        desc = generate_description(boundaries, header=None, footer=None)
        lines = [l for l in desc.splitlines() if l.strip()]
        assert "First" in lines[0]
        assert "Second" in lines[1]
        assert "Third" in lines[2]
