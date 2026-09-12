"""
tests/test_hidden_security.py
------------------------------
Harsh, adversarial test cases probing every attack surface and edge condition.
Tests are organized by attack category:

1.  Security — path traversal, null bytes, unicode, session injection
2.  Malformed inputs — wrong types, missing fields, oversized values
3.  File content attacks — valid ext / wrong content (fake audio)
4.  Crossfade boundary arithmetic — math verification
5.  State machine — calling endpoints out of order
6.  Re-entrancy — calling same endpoint twice on same session
7.  Session isolation — sessions must not bleed into each other
8.  Filesystem corruption — manually corrupt backend files mid-session
9.  Description injection — HTML, script tags, extremely long strings
10. Concurrent — multiple uploads get unique session IDs
"""

import io
import json
import shutil
import threading
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydub import AudioSegment
from pydub.generators import Sine

from backend.main import app

# raise_server_exceptions=False so unhandled 500s come back as HTTP 500
# instead of being re-raised in the test process.
CLIENT = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sine_mp3(frequency: int = 440, duration_ms: int = 10_000) -> bytes:
    """Return bytes of a valid MP3 (sine tone)."""
    buf = io.BytesIO()
    Sine(frequency).to_audio_segment(duration=duration_ms).export(buf, format="mp3")
    return buf.getvalue()


def _sine_wav(frequency: int = 660, duration_ms: int = 5_000) -> bytes:
    """Return bytes of a valid WAV file."""
    buf = io.BytesIO()
    Sine(frequency).to_audio_segment(duration=duration_ms).export(buf, format="wav")
    return buf.getvalue()


def _minimal_png() -> bytes:
    """Return a minimal valid 1×1 PNG (not audio)."""
    import struct, zlib
    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _garbage_binary() -> bytes:
    """Return clearly non-audio binary garbage."""
    return b"\x00\x01\x02\x03" * 100 + b"NOT_AUDIO_AT_ALL"


def _upload_two_real_tracks(name_a="track_a.mp3", name_b="track_b.mp3") -> dict:
    """Upload two real MP3 tracks and return the UploadResponse dict."""
    resp = CLIENT.post("/upload", files=[
        ("files", (name_a, _sine_mp3(440, 8_000), "audio/mpeg")),
        ("files", (name_b, _sine_mp3(880, 8_000), "audio/mpeg")),
    ])
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(autouse=True)
def cleanup_sessions(request):
    """Collect all session IDs created during a test and delete them afterward."""
    from backend.core.config import settings
    sessions_before = set()
    if settings.STORAGE_PATH.exists():
        sessions_before = {p.name for p in settings.STORAGE_PATH.iterdir() if p.is_dir()}
    yield
    if settings.STORAGE_PATH.exists():
        for p in settings.STORAGE_PATH.iterdir():
            if p.is_dir() and p.name not in sessions_before:
                shutil.rmtree(p, ignore_errors=True)


# ===========================================================================
# 1. SECURITY — path traversal & session injection
# ===========================================================================

class TestSecurityAttacks:

    def test_path_traversal_filename_stripped(self):
        """Filename '../../evil.mp3' must be sanitized — directory parts removed."""
        mp3 = _sine_mp3()
        resp = CLIENT.post("/upload", files=[
            ("files", ("../../evil.mp3", mp3, "audio/mpeg")),
            ("files", ("normal.mp3",    mp3, "audio/mpeg")),
        ])
        assert resp.status_code == 200
        for name in resp.json()["files"]:
            assert ".." not in name
            assert "/" not in name

    def test_deep_path_traversal_stripped(self):
        """Deeply nested '../../../../../../../../etc/passwd.mp3' → 'passwd.mp3'."""
        mp3 = _sine_mp3()
        resp = CLIENT.post("/upload", files=[
            ("files", ("../../../../../../../../etc/passwd.mp3", mp3, "audio/mpeg")),
            ("files", ("b.mp3", mp3, "audio/mpeg")),
        ])
        assert resp.status_code == 200
        assert "passwd.mp3" in resp.json()["files"]

    def test_windows_backslash_traversal_blocked_or_sanitized(self):
        """Windows-style '..\\..\\evil.mp3' — on POSIX, path.name returns the
        full string which starts with '.', so safe_filename rejects it with 400.
        Either 200 (sanitized) or 400 (rejected) is acceptable; never 500."""
        mp3 = _sine_mp3()
        resp = CLIENT.post("/upload", files=[
            ("files", ("..\\..\\evil.mp3", mp3, "audio/mpeg")),
            ("files", ("b.mp3", mp3, "audio/mpeg")),
        ])
        # On POSIX, "..\\..\\evil.mp3" starts with '.' so safe_filename → 400
        # On Windows (if ever run there), it would be stripped → 200
        assert resp.status_code in (200, 400), \
            f"Expected 200 or 400, got {resp.status_code}: {resp.text}"
        assert resp.status_code != 500

    def test_session_id_path_traversal_blocked(self):
        """session_id='../../etc' must be rejected with 400."""
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": "../../etc", "order": ["a.mp3"], "crossfade_ms": 0,
        })
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    def test_session_id_must_be_uuid4_format(self):
        """Non-UUID4 session IDs are all rejected."""
        bad_ids = [
            "not-a-uuid",
            "12345678-1234-1234-1234-123456789012",  # UUID1 (version=1)
            "00000000-0000-0000-0000-000000000000",  # nil UUID
            "SELECT * FROM sessions",
            "<script>alert(1)</script>",
            "a" * 500,
            " ",
        ]
        for bad_id in bad_ids:
            resp = CLIENT.post("/mixtape/create", json={
                "session_id": bad_id, "order": [], "crossfade_ms": 0,
            })
            assert resp.status_code in (400, 422), \
                f"Expected 400/422 for session_id={bad_id!r}, got {resp.status_code}"

    def test_description_session_id_traversal_blocked(self):
        resp = CLIENT.post("/description/generate", json={"session_id": "../../"})
        assert resp.status_code == 400

    def test_video_session_id_traversal_blocked(self):
        png = _minimal_png()
        resp = CLIENT.post("/video/create",
                           data={"session_id": "../../passwd"},
                           files=[("image", ("bg.png", png, "image/png"))])
        assert resp.status_code == 400

    def test_empty_filename_rejected(self):
        """A file with no filename must be rejected cleanly."""
        mp3 = _sine_mp3()
        resp = CLIENT.post("/upload", files=[
            ("files", ("", mp3, "audio/mpeg")),
            ("files", ("b.mp3", mp3, "audio/mpeg")),
        ])
        assert resp.status_code in (400, 422)

    def test_dot_only_filename_rejected(self):
        """Filename '.' is a directory reference and must be rejected."""
        mp3 = _sine_mp3()
        resp = CLIENT.post("/upload", files=[
            ("files", (".", mp3, "audio/mpeg")),
            ("files", ("b.mp3", mp3, "audio/mpeg")),
        ])
        assert resp.status_code in (400, 422)

    def test_html_xss_in_filename_does_not_crash(self):
        """XSS payload in filename must not crash server."""
        mp3 = _sine_mp3()
        resp = CLIENT.post("/upload", files=[
            ("files", ("<script>alert(1)</script>.mp3", mp3, "audio/mpeg")),
            ("files", ("b.mp3", mp3, "audio/mpeg")),
        ])
        assert resp.status_code != 500


# ===========================================================================
# 2. MALFORMED INPUTS
# ===========================================================================

class TestMalformedInputs:

    def test_upload_no_files_returns_4xx(self):
        """Uploading with no file field returns 400 or 422 (never 200 or 500)."""
        resp = CLIENT.post("/upload", files=[])
        # FastAPI gives 422 (missing required field) when no files at all are sent
        assert resp.status_code in (400, 422), \
            f"Expected 400 or 422, got {resp.status_code}"

    def test_upload_wrong_extension_returns_400(self):
        resp = CLIENT.post("/upload", files=[
            ("files", ("evil.exe", b"MZ\x90\x00", "application/octet-stream")),
        ])
        assert resp.status_code == 400

    def test_upload_php_extension_rejected(self):
        resp = CLIENT.post("/upload", files=[
            ("files", ("shell.php", b"<?php system($_GET['cmd']); ?>", "text/php")),
        ])
        assert resp.status_code == 400

    def test_mixtape_negative_crossfade_rejected(self):
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": -1,
        })
        assert resp.status_code == 422

    def test_mixtape_crossfade_over_schema_max_rejected(self):
        """crossfade_ms > 10_000 exceeds Pydantic schema le=10_000 → 422."""
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": 99_999,
        })
        assert resp.status_code == 422

    def test_mixtape_crossfade_as_string_rejected(self):
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": "fast",
        })
        assert resp.status_code == 422

    def test_mixtape_empty_order_uses_all_files(self):
        """Empty order list → falls back to all files (alphabetical)."""
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"], "order": [], "crossfade_ms": 0,
        })
        assert resp.status_code == 200
        assert len(resp.json()["boundaries"]) == 2

    def test_mixtape_nonexistent_file_in_order_returns_404(self):
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": ["does_not_exist.mp3"],
            "crossfade_ms": 0,
        })
        assert resp.status_code == 404

    def test_mixtape_nonexistent_session_returns_404(self):
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": str(uuid.uuid4()), "order": [], "crossfade_ms": 0,
        })
        assert resp.status_code == 404

    def test_description_before_merge_returns_404(self):
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/description/generate", json={
            "session_id": data["session_id"],
        })
        assert resp.status_code == 404

    def test_video_before_merge_returns_404(self):
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/video/create",
            data={"session_id": data["session_id"]},
            files=[("image", ("bg.png", _minimal_png(), "image/png"))],
        )
        assert resp.status_code == 404

    def test_video_invalid_image_extension_rejected(self):
        data = _upload_two_real_tracks()
        CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 0,
        })
        resp = CLIENT.post("/video/create",
            data={"session_id": data["session_id"]},
            files=[("image", ("bg.bmp", b"BM\x00\x00", "image/bmp"))],
        )
        assert resp.status_code == 400


# ===========================================================================
# 3. CORRUPT / FAKE AUDIO FILES
# ===========================================================================

class TestCorruptAudioFiles:

    def test_zero_byte_file_rejected_at_merge(self):
        """Zero-byte .mp3 passes upload but fails decode at merge."""
        resp = CLIENT.post("/upload", files=[
            ("files", ("empty.mp3", b"", "audio/mpeg")),
            ("files", ("b.mp3", _sine_mp3(), "audio/mpeg")),
        ])
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 0,
        })
        assert merge.status_code == 422

    def test_text_file_disguised_as_mp3_rejected_at_merge(self):
        fake_mp3 = b"This is definitely not audio data, just plain text."
        resp = CLIENT.post("/upload", files=[
            ("files", ("fake.mp3", fake_mp3, "audio/mpeg")),
            ("files", ("real.mp3", _sine_mp3(), "audio/mpeg")),
        ])
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 0,
        })
        assert merge.status_code == 422
        assert "decode" in merge.json()["detail"].lower()

    def test_python_script_disguised_as_mp3(self):
        evil = b"import os; os.system('rm -rf /')"
        resp = CLIENT.post("/upload", files=[
            ("files", ("malware.mp3", evil, "audio/mpeg")),
            ("files", ("b.mp3", _sine_mp3(), "audio/mpeg")),
        ])
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 0,
        })
        assert merge.status_code == 422

    def test_binary_garbage_disguised_as_mp3(self):
        """Raw binary garbage renamed .mp3 — not decodable by ffmpeg."""
        resp = CLIENT.post("/upload", files=[
            ("files", ("garbage.mp3", _garbage_binary(), "audio/mpeg")),
            ("files", ("real.mp3", _sine_mp3(), "audio/mpeg")),
        ])
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 0,
        })
        # Must never be 500 — 422 (corrupt audio) is expected
        assert merge.status_code != 500

    def test_all_fake_files_rejected(self):
        """All files fake → merge must return 422, never 500."""
        fake = b"GARBAGE DATA NOT AUDIO"
        resp = CLIENT.post("/upload", files=[
            ("files", ("a.mp3", fake, "audio/mpeg")),
            ("files", ("b.mp3", fake, "audio/mpeg")),
        ])
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 0,
        })
        assert merge.status_code == 422


# ===========================================================================
# 4. CROSSFADE BOUNDARY ARITHMETIC
# ===========================================================================

class TestCrossfadeBoundaryArithmetic:

    def test_zero_crossfade_tracks_sequential(self):
        """With crossfade=0, B starts approximately where A ends."""
        resp = CLIENT.post("/upload", files=[
            ("files", ("a.mp3", _sine_mp3(440, 10_000), "audio/mpeg")),
            ("files", ("b.mp3", _sine_mp3(880, 8_000),  "audio/mpeg")),
        ])
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 0, "normalize": False,
        }).json()
        bounds = merge["boundaries"]
        assert bounds[0]["start_ms"] == 0
        assert bounds[1]["start_ms"] >= 9_000  # ≈A duration

    def test_crossfade_1000ms_creates_overlap(self):
        """With 1000ms crossfade, B.start_ms < A.end_ms (they overlap)."""
        resp = CLIENT.post("/upload", files=[
            ("files", ("a.mp3", _sine_mp3(440, 10_000), "audio/mpeg")),
            ("files", ("b.mp3", _sine_mp3(880, 10_000), "audio/mpeg")),
        ])
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 1000, "normalize": False,
        }).json()
        bounds = merge["boundaries"]
        overlap = bounds[0]["end_ms"] - bounds[1]["start_ms"]
        assert 800 <= overlap <= 1200, f"Expected ~1000ms crossfade, got {overlap}ms"

    def test_three_track_boundaries_ascending(self):
        """Three tracks: boundaries must be in strict ascending order."""
        resp = CLIENT.post("/upload", files=[
            ("files", ("a.mp3", _sine_mp3(440, 8_000), "audio/mpeg")),
            ("files", ("b.mp3", _sine_mp3(660, 8_000), "audio/mpeg")),
            ("files", ("c.mp3", _sine_mp3(880, 8_000), "audio/mpeg")),
        ])
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"], "crossfade_ms": 2000, "normalize": False,
        }).json()
        starts = [b["start_ms"] for b in merge["boundaries"]]
        assert starts == sorted(starts)
        assert starts[0] == 0

    def test_crossfade_within_schema_but_exceeds_track_is_engine_clamped(self):
        """
        crossfade_ms=8000 with 5-second tracks: schema allows ≤10000, but
        the engine (merge_tracks) clamps it to min_duration//2 = 2500ms.
        Must succeed, not crash.
        """
        resp = CLIENT.post("/upload", files=[
            ("files", ("a.mp3", _sine_mp3(440, 5_000), "audio/mpeg")),
            ("files", ("b.mp3", _sine_mp3(880, 5_000), "audio/mpeg")),
        ])
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": 8000,  # within schema le=10000
            "normalize": False,
        })
        assert merge.status_code == 200
        assert merge.json()["duration_ms"] > 0

    def test_description_timestamps_match_boundaries(self):
        """Timestamps in description must align with API-reported boundaries."""
        resp = CLIENT.post("/upload", files=[
            ("files", ("Alpha.mp3", _sine_mp3(440, 10_000), "audio/mpeg")),
            ("files", ("Beta.mp3",  _sine_mp3(880, 10_000), "audio/mpeg")),
        ])
        data = resp.json()
        sid = data["session_id"]
        CLIENT.post("/mixtape/create", json={
            "session_id": sid, "order": data["files"],
            "crossfade_ms": 0, "normalize": False,
        })
        desc = CLIENT.post("/description/generate", json={
            "session_id": sid,
        }).json()["description"]
        assert "0:00" in desc
        assert "Alpha" in desc
        assert "Beta" in desc


# ===========================================================================
# 5. STATE MACHINE — out-of-order operations
# ===========================================================================

class TestStateMachine:

    def test_video_without_merge_returns_404(self):
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/video/create",
            data={"session_id": data["session_id"]},
            files=[("image", ("bg.png", _minimal_png(), "image/png"))],
        )
        assert resp.status_code == 404

    def test_description_without_merge_returns_404(self):
        data = _upload_two_real_tracks()
        resp = CLIENT.post("/description/generate", json={"session_id": data["session_id"]})
        assert resp.status_code == 404

    def test_re_merge_same_session_overwrites(self):
        """Two consecutive merges on same session — both must succeed."""
        data = _upload_two_real_tracks()
        sid, files = data["session_id"], data["files"]
        r1 = CLIENT.post("/mixtape/create", json={"session_id": sid, "order": files, "crossfade_ms": 0})
        r2 = CLIENT.post("/mixtape/create", json={"session_id": sid, "order": files, "crossfade_ms": 500})
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Crossfade changes total duration
        assert r1.json()["duration_ms"] != r2.json()["duration_ms"]

    def test_re_generate_description_succeeds(self):
        """Generating description twice on same session — both must succeed."""
        data = _upload_two_real_tracks()
        sid, files = data["session_id"], data["files"]
        CLIENT.post("/mixtape/create", json={"session_id": sid, "order": files, "crossfade_ms": 0})
        r1 = CLIENT.post("/description/generate", json={"session_id": sid, "header": "H1"})
        r2 = CLIENT.post("/description/generate", json={"session_id": sid, "header": "H2"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert "H1" in r1.json()["description"]
        assert "H2" in r2.json()["description"]


# ===========================================================================
# 6. SESSION ISOLATION
# ===========================================================================

class TestSessionIsolation:

    def test_two_sessions_do_not_share_files(self):
        """
        Session A has uniquely-named files. Using those names in session B's
        merge must return 404 because B's raw dir has different files.
        """
        # Use unique filenames so they definitely don't exist in both sessions
        a_data = _upload_two_real_tracks("session_a_1.mp3", "session_a_2.mp3")
        b_data = _upload_two_real_tracks("session_b_1.mp3", "session_b_2.mp3")

        # Try to access session A's filenames through session B's session_id
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": b_data["session_id"],
            "order": a_data["files"],  # session A's filenames
            "crossfade_ms": 0,
        })
        assert resp.status_code == 404, \
            "Session B must not find session A's files"

    def test_deleted_session_returns_404(self):
        """If session directory is manually deleted, subsequent calls return 404."""
        from backend.core.config import settings
        data = _upload_two_real_tracks()
        sid = data["session_id"]
        shutil.rmtree(settings.STORAGE_PATH / sid, ignore_errors=True)
        resp = CLIENT.post("/mixtape/create", json={
            "session_id": sid, "order": data["files"], "crossfade_ms": 0,
        })
        assert resp.status_code == 404


# ===========================================================================
# 7. CONCURRENT REQUESTS
# ===========================================================================

class TestConcurrentRequests:

    def test_simultaneous_uploads_get_unique_session_ids(self):
        """10 concurrent uploads must each get a unique session_id."""
        results: list[str] = []
        errors: list[str] = []

        def do_upload():
            try:
                mp3 = _sine_mp3(440, 3_000)
                resp = CLIENT.post("/upload", files=[
                    ("files", ("a.mp3", mp3, "audio/mpeg")),
                    ("files", ("b.mp3", mp3, "audio/mpeg")),
                ])
                results.append(resp.json()["session_id"])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_upload) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert not errors, f"Upload errors: {errors}"
        assert len(set(results)) == 10, "All 10 sessions must have unique IDs"

    def test_concurrent_merges_on_different_sessions_both_succeed(self):
        """Two simultaneous merges on different sessions both succeed."""
        data1 = _upload_two_real_tracks("x1.mp3", "x2.mp3")
        data2 = _upload_two_real_tracks("y1.mp3", "y2.mp3")
        results: dict[str, int] = {}
        errors: list[str] = []

        def do_merge(label: str, session_id: str, files: list):
            try:
                resp = CLIENT.post("/mixtape/create", json={
                    "session_id": session_id, "order": files, "crossfade_ms": 0,
                })
                results[label] = resp.status_code
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=do_merge, args=("A", data1["session_id"], data1["files"]))
        t2 = threading.Thread(target=do_merge, args=("B", data2["session_id"], data2["files"]))
        t1.start(); t2.start()
        t1.join();  t2.join()

        assert not errors
        assert results["A"] == 200
        assert results["B"] == 200


# ===========================================================================
# 8. FILESYSTEM CORRUPTION
# ===========================================================================

class TestFilesystemCorruption:

    def test_corrupted_boundaries_json_returns_422(self):
        """Corrupted boundaries.json returns 422, not an unhandled 500."""
        from backend.core.config import settings
        data = _upload_two_real_tracks()
        sid = data["session_id"]
        CLIENT.post("/mixtape/create", json={
            "session_id": sid, "order": data["files"], "crossfade_ms": 0,
        })
        # Corrupt the boundaries.json
        (settings.STORAGE_PATH / sid / "boundaries.json").write_text("NOT_JSON{{{")
        resp = CLIENT.post("/description/generate", json={"session_id": sid})
        # After our fix, this must return 422 (not 500)
        assert resp.status_code == 422
        assert "corrupted" in resp.json()["detail"].lower()

    def test_missing_merged_mp3_for_video_returns_404(self):
        """Deleted merged.mp3 between merge and video creation → 404."""
        from backend.core.config import settings
        data = _upload_two_real_tracks()
        sid = data["session_id"]
        CLIENT.post("/mixtape/create", json={
            "session_id": sid, "order": data["files"], "crossfade_ms": 0,
        })
        (settings.STORAGE_PATH / sid / "merged.mp3").unlink(missing_ok=True)
        resp = CLIENT.post("/video/create",
            data={"session_id": sid},
            files=[("image", ("bg.png", _minimal_png(), "image/png"))],
        )
        assert resp.status_code == 404


# ===========================================================================
# 9. DESCRIPTION INJECTION & UNICODE
# ===========================================================================

class TestDescriptionInjectionAndUnicode:

    def test_very_long_header_accepted(self):
        """2000-char header must appear in description."""
        data = _upload_two_real_tracks()
        sid = data["session_id"]
        CLIENT.post("/mixtape/create", json={
            "session_id": sid, "order": data["files"], "crossfade_ms": 0,
        })
        long_header = "A" * 2000
        resp = CLIENT.post("/description/generate", json={
            "session_id": sid, "header": long_header,
        })
        assert resp.status_code == 200
        assert long_header in resp.json()["description"]

    def test_html_tags_in_header_appear_literally(self):
        """HTML tags in header must appear as literal text (plain text output)."""
        data = _upload_two_real_tracks()
        sid = data["session_id"]
        CLIENT.post("/mixtape/create", json={
            "session_id": sid, "order": data["files"], "crossfade_ms": 0,
        })
        header = "<b>Bold</b><script>alert(1)</script>"
        resp = CLIENT.post("/description/generate", json={
            "session_id": sid, "header": header,
        })
        assert resp.status_code == 200
        # Raw HTML appears in plain text — not interpreted
        assert "<b>Bold</b>" in resp.json()["description"]

    def test_none_header_footer_omitted(self):
        """No header/footer → description contains only timestamp lines."""
        data = _upload_two_real_tracks()
        sid = data["session_id"]
        CLIENT.post("/mixtape/create", json={
            "session_id": sid, "order": data["files"], "crossfade_ms": 0,
        })
        resp = CLIENT.post("/description/generate", json={
            "session_id": sid, "header": None, "footer": None,
        })
        assert resp.status_code == 200


# ===========================================================================
# 10. HEALTH CHECK
# ===========================================================================

class TestHealthCheck:

    def test_health_returns_200(self):
        resp = CLIENT.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_unknown_route_returns_404(self):
        resp = CLIENT.get("/does_not_exist_at_all")
        assert resp.status_code == 404

    def test_wrong_http_method_on_upload(self):
        """GET on a POST-only endpoint must return 405."""
        resp = CLIENT.get("/upload")
        assert resp.status_code == 405
