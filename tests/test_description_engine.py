"""
tests/test_description_engine.py
----------------------------------
Unit tests for backend/services/description_engine.py

These are the simplest tests in the project — pure string logic, zero I/O.
They are the fastest-running tests and the best ones to write first.

Run with:
    uv run pytest tests/test_description_engine.py -v
"""

import pytest

from backend.services.audio_engine import TrackBoundary
from backend.services.description_engine import format_timestamp, generate_description


# ---------------------------------------------------------------------------
# format_timestamp
# ---------------------------------------------------------------------------

class TestFormatTimestamp:
    """
    Edge cases to verify:
        0ms          → "0:00"
        59,999ms     → "0:59"   (just under 1 minute)
        60,000ms     → "1:00"
        225,000ms    → "3:45"   (3 min 45 sec)
        3,599,000ms  → "59:59"  (just under 1 hour)
        3,600,000ms  → "1:00:00" (exactly 1 hour)
        3_705_000ms  → "1:01:45"
    """

    @pytest.mark.parametrize("ms,expected", [
        (0,           "0:00"),
        (1_000,       "0:01"),
        (59_000,      "0:59"),
        (60_000,      "1:00"),
        (225_000,     "3:45"),
        (3_599_000,   "59:59"),
        (3_600_000,   "1:00:00"),
        (3_705_000,   "1:01:45"),
        (7_322_000,   "2:02:02"),
        (-500,        "0:00"),   # negative ms → clamp to 0
    ])
    def test_format_timestamp(self, ms: int, expected: str):
        assert format_timestamp(ms) == expected


# ---------------------------------------------------------------------------
# generate_description
# ---------------------------------------------------------------------------

class TestGenerateDescription:
    def _make_boundaries(self) -> list[TrackBoundary]:
        return [
            TrackBoundary(name="Track One",   start_ms=0,       end_ms=225_000),
            TrackBoundary(name="Track Two",   start_ms=222_000, end_ms=480_000),
            TrackBoundary(name="Track Three", start_ms=477_000, end_ms=720_000),
        ]

    def test_timestamps_appear_in_output(self):
        boundaries = self._make_boundaries()
        result = generate_description(boundaries, header=None, footer=None)
        assert "0:00 Track One" in result
        assert "3:42 Track Two" in result    # 222,000ms = 3m42s
        assert "7:57 Track Three" in result  # 477,000ms = 7m57s

    def test_default_header_appears(self):
        boundaries = self._make_boundaries()
        result = generate_description(boundaries)
        assert "🎵 Mixtape Tracklist" in result

    def test_default_footer_appears(self):
        boundaries = self._make_boundaries()
        result = generate_description(boundaries)
        assert "#mixtape #music" in result

    def test_no_header(self):
        boundaries = self._make_boundaries()
        result = generate_description(boundaries, header=None, footer=None)
        assert "🎵" not in result
        assert result.startswith("0:00 Track One")

    def test_no_footer(self):
        boundaries = self._make_boundaries()
        result = generate_description(boundaries, header=None, footer=None)
        assert "#mixtape" not in result

    def test_custom_header_footer(self):
        boundaries = self._make_boundaries()
        result = generate_description(
            boundaries, header="MY HEADER\n", footer="\nMY FOOTER"
        )
        assert result.startswith("MY HEADER")
        assert result.endswith("MY FOOTER")

    def test_single_track(self):
        boundaries = [TrackBoundary(name="Solo", start_ms=0, end_ms=300_000)]
        result = generate_description(boundaries, header=None, footer=None)
        assert result.strip() == "0:00 Solo"

    def test_track_order_preserved(self):
        boundaries = self._make_boundaries()
        result = generate_description(boundaries, header=None, footer=None)
        lines = result.strip().split("\n")
        assert lines[0].endswith("Track One")
        assert lines[1].endswith("Track Two")
        assert lines[2].endswith("Track Three")

    def test_over_one_hour_timestamp(self):
        boundaries = [
            TrackBoundary(name="Intro",  start_ms=0,         end_ms=3_600_000),
            TrackBoundary(name="Part 2", start_ms=3_600_000, end_ms=7_200_000),
        ]
        result = generate_description(boundaries, header=None, footer=None)
        assert "1:00:00 Part 2" in result
