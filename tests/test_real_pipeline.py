"""
tests/test_real_pipeline.py
-----------------------------
The harshest test: a full end-to-end pipeline using REAL audio + video generated
by ffmpeg — no mocks, no stubs, no fake bytes.

Pipeline:
  1. Generate 3 MP3 files (sine tones, different pitches/durations) via ffmpeg
  2. Generate a 1920×1080 JPEG background via ffmpeg
  3. Upload all 3 tracks → POST /upload
  4. Merge with 2-second crossfade → POST /mixtape/create
  5. Verify merged.mp3 on disk with ffprobe
  6. Generate description → POST /description/generate
  7. Verify timestamp format and track names
  8. Create MP4 video → POST /video/create
  9. Verify MP4 with ffprobe (codec, duration, resolution, pixel format)
  10. Download both files via static URL
  11. Verify boundaries.json structure on disk

All cleanup is done by the class-scoped `pipeline_state` fixture after the
entire class finishes — sessions are NOT deleted between individual tests.
"""

import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydub.generators import Sine

from backend.main import app
from backend.core.config import settings

CLIENT = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------
FFMPEG  = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(
    not FFMPEG,
    reason="ffmpeg not installed — skipping real pipeline tests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ffprobe_info(path: str) -> dict:
    """Run ffprobe and return parsed JSON (format + streams)."""
    cmd = [FFPROBE, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"ffprobe failed on {path}: {r.stderr}"
    return json.loads(r.stdout)


def generate_mp3_via_ffmpeg(tmp_dir: Path, name: str, freq: int, duration: int) -> bytes:
    """Generate a real MP3 via ffmpeg lavfi sine source."""
    out = tmp_dir / name
    r = subprocess.run(
        [FFMPEG, "-f", "lavfi", "-i",
         f"sine=frequency={freq}:duration={duration}",
         "-ar", "44100", "-ac", "2", "-b:a", "128k", str(out), "-y"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"ffmpeg audio generation failed: {r.stderr}"
    assert out.stat().st_size > 0
    return out.read_bytes()


def generate_jpeg_via_ffmpeg(tmp_dir: Path) -> bytes:
    """Generate a real 1920×1080 JPEG via ffmpeg."""
    out = tmp_dir / "background.jpg"
    r = subprocess.run(
        [FFMPEG, "-f", "lavfi", "-i",
         "color=c=#1a1a2e:size=1920x1080:rate=1",
         "-vframes", "1", str(out), "-y"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"ffmpeg image generation failed: {r.stderr}"
    assert out.stat().st_size > 0
    return out.read_bytes()


# ---------------------------------------------------------------------------
# Class-scoped shared state fixture
# ---------------------------------------------------------------------------

class PipelineState:
    """Mutable bag passed between all tests in TestRealPipeline."""
    session_id: str = ""
    files: list[str] = []
    merge_response: dict = {}
    description_text: str = ""
    video_url: str = ""
    bg_bytes: bytes = b""
    audio_bytes: dict[str, bytes] = {}


# Registry of sessions owned by long-lived fixtures — never auto-deleted mid-test
_protected_sessions: set[str] = set()


@pytest.fixture(scope="class")
def pipeline_state(tmp_path_factory, request):
    """
    Runs once per class:
      - Generates all real assets with ffmpeg
      - Cleans up the session directory after all tests in the class finish
    """
    tmp = tmp_path_factory.mktemp("real_pipeline")
    state = PipelineState()

    # Pre-generate assets so tests don't re-run ffmpeg
    state.audio_bytes = {
        "low.mp3":  generate_mp3_via_ffmpeg(tmp, "low.mp3",  220, 12),  # 12s
        "mid.mp3":  generate_mp3_via_ffmpeg(tmp, "mid.mp3",  440, 10),  # 10s
        "high.mp3": generate_mp3_via_ffmpeg(tmp, "high.mp3", 880,  8),  # 8s
    }
    state.bg_bytes = generate_jpeg_via_ffmpeg(tmp)

    yield state

    # Teardown: unprotect and remove session directory
    if state.session_id:
        _protected_sessions.discard(state.session_id)
        shutil.rmtree(settings.STORAGE_PATH / state.session_id, ignore_errors=True)


# ---------------------------------------------------------------------------
# Per-test session cleanup (skips protected sessions)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_extra_sessions():
    """
    Track and clean up any sessions created OUTSIDE of pipeline_state.
    Sessions registered in _protected_sessions are left alone.
    """
    before = set()
    if settings.STORAGE_PATH.exists():
        before = {p.name for p in settings.STORAGE_PATH.iterdir() if p.is_dir()}
    yield
    if settings.STORAGE_PATH.exists():
        for p in settings.STORAGE_PATH.iterdir():
            if (
                p.is_dir()
                and p.name not in before
                and p.name not in _protected_sessions
            ):
                shutil.rmtree(p, ignore_errors=True)


# ===========================================================================
# THE REAL END-TO-END PIPELINE
# ===========================================================================

class TestRealPipeline:
    """
    7 tests share the SAME session via the class-scoped pipeline_state fixture.
    Tests run in alphabetical order so test_01_* runs before test_02_*, etc.
    """

    # ── Step 1: Upload ───────────────────────────────────────────────────────

    def test_01_upload_three_real_mp3s(self, pipeline_state: PipelineState):
        """Upload 3 real ffmpeg-generated MP3s, verify session created on disk."""
        files_payload = [
            ("files", (name, data, "audio/mpeg"))
            for name, data in pipeline_state.audio_bytes.items()
        ]
        resp = CLIENT.post("/upload", files=files_payload)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"

        body = resp.json()
        assert len(body["files"]) == 3
        assert body["count"] == 3

        sid = body["session_id"]
        # Must be UUID4
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            sid,
        ), f"session_id not UUID4: {sid}"

        # Files must exist on disk
        for fname in body["files"]:
            p = settings.STORAGE_PATH / sid / "raw" / fname
            assert p.exists() and p.stat().st_size > 0, f"Missing: {p}"

        # Store state for subsequent tests — also protect from autouse cleanup
        pipeline_state.session_id = sid
        pipeline_state.files = body["files"]
        _protected_sessions.add(sid)  # ← prevents cleanup_extra_sessions from deleting this

    # ── Step 2: Create Mixtape ───────────────────────────────────────────────

    def test_02_create_mixtape_with_crossfade(self, pipeline_state: PipelineState):
        """Merge 3 real tracks with 2-second crossfade; verify duration math."""
        sid = pipeline_state.session_id
        assert sid, "test_01 must pass first"

        resp = CLIENT.post("/mixtape/create", json={
            "session_id": sid,
            "order": pipeline_state.files,
            "crossfade_ms": 2000,
            "normalize": True,
        })
        assert resp.status_code == 200, f"Merge failed: {resp.text}"
        body = resp.json()

        # Duration = 12000 + 10000 + 8000 - 2000 - 2000 = 26000ms
        expected = 12_000 + 10_000 + 8_000 - 2_000 - 2_000
        actual = body["duration_ms"]
        assert abs(actual - expected) < 2_000, (
            f"Expected ~{expected}ms, got {actual}ms (diff={abs(actual-expected)}ms)"
        )

        # Boundaries: ascending, first at 0, each overlaps previous
        bounds = body["boundaries"]
        assert len(bounds) == 3
        assert bounds[0]["start_ms"] == 0
        starts = [b["start_ms"] for b in bounds]
        assert starts == sorted(starts)

        # Each track overlaps the previous (crossfade)
        for i in range(1, len(bounds)):
            overlap = bounds[i - 1]["end_ms"] - bounds[i]["start_ms"]
            assert overlap > 0, f"Track {i} must overlap previous"

        # merged.mp3 on disk
        merged_path = settings.STORAGE_PATH / sid / "merged.mp3"
        assert merged_path.exists()
        assert merged_path.stat().st_size > 50_000

        # ffprobe: must be a valid audio file
        probe = ffprobe_info(str(merged_path))
        audio_streams = [s for s in probe["streams"] if s.get("codec_type") == "audio"]
        assert len(audio_streams) >= 1
        assert audio_streams[0]["codec_name"] in ("mp3", "mp3float")

        pipeline_state.merge_response = body
        print(f"\n✅ merged.mp3 — {merged_path.stat().st_size:,} bytes, "
              f"{actual}ms ({actual/1000:.1f}s)")

    # ── Step 3: Generate Description ────────────────────────────────────────

    def test_03_generate_description(self, pipeline_state: PipelineState):
        """Generate description; verify all timestamps, names, custom header/footer."""
        sid = pipeline_state.session_id
        assert sid

        resp = CLIENT.post("/description/generate", json={
            "session_id": sid,
            "header": "🎵 Real Pipeline Test\n",
            "footer": "\n\n#test #mixtape",
        })
        assert resp.status_code == 200, f"Description failed: {resp.text}"
        desc = resp.json()["description"]

        assert "Real Pipeline Test" in desc
        assert "#test #mixtape" in desc

        # All 3 track names must appear
        for fname in pipeline_state.files:
            stem = Path(fname).stem
            assert stem in desc, f"Track '{stem}' missing from description"

        # At least 3 timestamps in M:SS or H:MM:SS format
        ts_matches = re.findall(r"\d+:\d{2}(?::\d{2})?", desc)
        assert len(ts_matches) >= 3, f"Expected ≥3 timestamps, found: {ts_matches}"

        # First track must be at 0:00
        assert "0:00" in desc

        pipeline_state.description_text = desc
        print(f"\n✅ Description ({len(desc)} chars):\n{desc[:200]}…")

    # ── Step 4: Create Video ────────────────────────────────────────────────

    def test_04_create_mp4_video_and_verify_with_ffprobe(self, pipeline_state: PipelineState):
        """
        Encode real MP4; verify with ffprobe:
          - Has video stream (h264) and audio stream (aac)
          - Pixel format is yuv420p
          - Width and height are both even (libx264 requirement)
          - Duration within 5% of merged audio
        """
        sid = pipeline_state.session_id
        assert sid

        resp = CLIENT.post("/video/create",
            data={"session_id": sid},
            files=[("image", ("background.jpg", pipeline_state.bg_bytes, "image/jpeg"))],
        )
        assert resp.status_code == 200, f"Video creation failed: {resp.text}"
        body = resp.json()
        assert body["video_url"].endswith(".mp4")

        video_path = settings.STORAGE_PATH / sid / "mixtape.mp4"
        assert video_path.exists()
        size = video_path.stat().st_size
        assert size > 100_000, f"mixtape.mp4 too small: {size} bytes"

        # ── ffprobe deep validation ──────────────────────────────────────────
        probe = ffprobe_info(str(video_path))
        streams = probe["streams"]
        v_streams = [s for s in streams if s.get("codec_type") == "video"]
        a_streams = [s for s in streams if s.get("codec_type") == "audio"]

        assert len(v_streams) >= 1, "No video stream in MP4"
        assert len(a_streams) >= 1, "No audio stream in MP4"

        vs = v_streams[0]
        as_ = a_streams[0]

        assert vs["codec_name"] == "h264", f"Expected h264, got {vs['codec_name']}"
        assert as_["codec_name"] == "aac",  f"Expected aac,  got {as_['codec_name']}"
        # Accept both yuv420p and yuvj420p (JPEG full-range variant — YouTube compatible)
        assert vs["pix_fmt"] in ("yuv420p", "yuvj420p"), \
            f"Expected yuv420p or yuvj420p, got {vs['pix_fmt']}"

        width  = int(vs["width"])
        height = int(vs["height"])
        assert width  % 2 == 0, f"Width must be even: {width}"
        assert height % 2 == 0, f"Height must be even: {height}"

        # Duration check: within 5% of audio duration
        video_dur_s = float(probe["format"]["duration"])
        expected_dur_s = pipeline_state.merge_response["duration_ms"] / 1000
        tol = expected_dur_s * 0.05
        assert abs(video_dur_s - expected_dur_s) < tol, (
            f"Video {video_dur_s:.1f}s vs audio {expected_dur_s:.1f}s "
            f"(diff={abs(video_dur_s - expected_dur_s):.1f}s, tol={tol:.1f}s)"
        )

        pipeline_state.video_url = body["video_url"]
        print(f"\n✅ mixtape.mp4 — {size/1024/1024:.1f} MB, "
              f"{width}×{height}, {video_dur_s:.1f}s")

    # ── Step 5: Download merged.mp3 via static URL ───────────────────────────

    def test_05_merged_audio_downloadable_via_static_url(self, pipeline_state: PipelineState):
        """GET /storage/{sid}/merged.mp3 must return valid audio bytes."""
        sid = pipeline_state.session_id
        assert sid

        resp = CLIENT.get(f"/storage/{sid}/merged.mp3")
        assert resp.status_code == 200, f"merged.mp3 download failed: {resp.status_code}"
        assert len(resp.content) > 50_000

    # ── Step 6: Download mixtape.mp4 via static URL ──────────────────────────

    def test_06_mp4_downloadable_via_static_url(self, pipeline_state: PipelineState):
        """GET /storage/{sid}/mixtape.mp4 must return valid video bytes."""
        sid = pipeline_state.session_id
        assert sid

        resp = CLIENT.get(f"/storage/{sid}/mixtape.mp4")
        assert resp.status_code == 200, f"mixtape.mp4 download failed: {resp.status_code}"
        assert len(resp.content) > 100_000

    # ── Step 7: boundaries.json structure ────────────────────────────────────

    def test_07_boundaries_json_on_disk_is_valid(self, pipeline_state: PipelineState):
        """boundaries.json must be valid JSON with correct schema and ordering."""
        sid = pipeline_state.session_id
        assert sid

        p = settings.STORAGE_PATH / sid / "boundaries.json"
        assert p.exists(), "boundaries.json not found"

        data = json.loads(p.read_text())
        assert isinstance(data, list) and len(data) == 3

        for i, b in enumerate(data):
            assert "name"     in b, f"Boundary {i} missing 'name'"
            assert "start_ms" in b, f"Boundary {i} missing 'start_ms'"
            assert "end_ms"   in b, f"Boundary {i} missing 'end_ms'"
            assert isinstance(b["start_ms"], int) and b["start_ms"] >= 0
            assert isinstance(b["end_ms"],   int) and b["end_ms"]   > b["start_ms"]

        starts = [b["start_ms"] for b in data]
        assert starts == sorted(starts), "Boundaries not in ascending order"
        assert starts[0] == 0, "First boundary must start at 0"


# ===========================================================================
# Normalization accuracy tests (isolated sessions)
# ===========================================================================

class TestNormalizationAccuracy:

    def _upload_merge(self, files):
        resp = CLIENT.post("/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": 0,
            "normalize": True,
        })
        return merge

    def test_normalize_on_succeeds_with_quiet_and_loud_tracks(self):
        """normalize=True with a very quiet and a very loud track must not crash."""
        quiet_buf = io.BytesIO()
        loud_buf  = io.BytesIO()
        Sine(440).to_audio_segment(duration=5_000).apply_gain(-30).export(quiet_buf, format="mp3")
        Sine(880).to_audio_segment(duration=5_000).apply_gain(0).export(loud_buf,  format="mp3")

        merge = self._upload_merge([
            ("files", ("quiet.mp3", quiet_buf.getvalue(), "audio/mpeg")),
            ("files", ("loud.mp3",  loud_buf.getvalue(),  "audio/mpeg")),
        ])
        assert merge.status_code == 200
        assert merge.json()["duration_ms"] > 0

    def test_silence_track_with_normalize_does_not_produce_nan(self):
        """
        Silence track (dBFS = -inf) with normalize=True: the old bug was
        apply_gain(+inf) → NaN samples → export → import → wrong duration.
        After the fix: silence is returned unchanged, no NaN.
        """
        silence_buf = io.BytesIO()
        real_buf    = io.BytesIO()
        AudioSegment.silent(duration=5_000).export(silence_buf, format="wav")
        Sine(440).to_audio_segment(duration=5_000).export(real_buf, format="mp3")

        resp = CLIENT.post("/upload", files=[
            ("files", ("silence.wav", silence_buf.getvalue(), "audio/wav")),
            ("files", ("real.mp3",    real_buf.getvalue(),    "audio/mpeg")),
        ])
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": 0,
            "normalize": True,
        })
        assert merge.status_code == 200
        # Duration must be > 0 (NaN audio would produce 0 or corrupt duration)
        assert merge.json()["duration_ms"] > 0

    def test_normalize_off_also_produces_valid_output(self):
        """normalize=False — just concatenate, no gain changes."""
        buf_a = io.BytesIO()
        buf_b = io.BytesIO()
        Sine(440).to_audio_segment(duration=5_000).export(buf_a, format="mp3")
        Sine(880).to_audio_segment(duration=5_000).export(buf_b, format="mp3")

        merge = self._upload_merge([
            ("files", ("a.mp3", buf_a.getvalue(), "audio/mpeg")),
            ("files", ("b.mp3", buf_b.getvalue(), "audio/mpeg")),
        ])
        assert merge.status_code == 200


# ===========================================================================
# Multi-format tests
# ===========================================================================

class TestMultipleAudioFormats:

    def _upload_and_merge(self, files):
        resp = CLIENT.post("/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": 0,
        })
        return merge

    def test_wav_files_merge_successfully(self):
        buf_a = io.BytesIO(); Sine(440).to_audio_segment(duration=5_000).export(buf_a, format="wav")
        buf_b = io.BytesIO(); Sine(880).to_audio_segment(duration=5_000).export(buf_b, format="wav")
        merge = self._upload_and_merge([
            ("files", ("a.wav", buf_a.getvalue(), "audio/wav")),
            ("files", ("b.wav", buf_b.getvalue(), "audio/wav")),
        ])
        assert merge.status_code == 200

    def test_mixed_wav_mp3_merge_successfully(self):
        buf_mp3 = io.BytesIO(); Sine(440).to_audio_segment(duration=5_000).export(buf_mp3, format="mp3")
        buf_wav = io.BytesIO(); Sine(880).to_audio_segment(duration=5_000).export(buf_wav, format="wav")
        merge = self._upload_and_merge([
            ("files", ("a.mp3", buf_mp3.getvalue(), "audio/mpeg")),
            ("files", ("b.wav", buf_wav.getvalue(), "audio/wav")),
        ])
        assert merge.status_code == 200

    def test_single_track_merge_succeeds(self):
        """Merging 1 track is valid — output is just that track."""
        buf = io.BytesIO()
        Sine(440).to_audio_segment(duration=5_000).export(buf, format="mp3")
        resp = CLIENT.post("/upload", files=[
            ("files", ("solo.mp3", buf.getvalue(), "audio/mpeg")),
        ])
        assert resp.status_code == 200
        data = resp.json()
        merge = CLIENT.post("/mixtape/create", json={
            "session_id": data["session_id"],
            "order": data["files"],
            "crossfade_ms": 0,
        })
        assert merge.status_code == 200
        assert len(merge.json()["boundaries"]) == 1
        assert merge.json()["boundaries"][0]["start_ms"] == 0


# The missing import that was causing NameError in the old file
from pydub import AudioSegment
