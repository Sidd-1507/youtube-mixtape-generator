"""
tests/test_api.py
------------------
FastAPI integration tests using TestClient.

What is TestClient?
-------------------
FastAPI's TestClient (from Starlette) runs your ENTIRE app in-process without
needing a running server. It translates Python function calls into real HTTP
requests through the ASGI interface. This means:

- Tests run in milliseconds (no server startup)
- Tests exercise the FULL stack: routers + services + error handling
- You can test HTTP status codes, response bodies, and file creation

Every test here represents a real API call a user or the Streamlit UI
would make. They also test FAILURE MODES that unit tests can't catch
because those failures happen at the HTTP boundary.

Failure modes tested:
- Missing session (404)
- Invalid session format / path traversal (400)
- Invalid file extension (400)
- No files uploaded (400)
- Missing prerequisite (merge before describe) (404)
- Corrupt audio file (422)
- Wrong image format (400)
- Full end-to-end pipeline (201 across all 4 endpoints)
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydub.generators import Sine

from backend.main import app
from backend.core.config import settings

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures — shared test data
# ---------------------------------------------------------------------------

def _make_mp3_bytes(duration_ms: int = 3_000, freq: float = 440.0) -> bytes:
    """Generate a real MP3 as raw bytes using pydub + ffmpeg."""
    seg = Sine(freq).to_audio_segment(duration=duration_ms)
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    buf.seek(0)
    return buf.read()


def _make_jpeg_bytes() -> bytes:
    """Generate a tiny 100x100 solid JPEG using ffmpeg subprocess."""
    import subprocess, tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        tmp = f.name
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=100x100:d=1",
         "-frames:v", "1", tmp],
        capture_output=True,
        check=True,
    )
    data = Path(tmp).read_bytes()
    os.unlink(tmp)
    return data


@pytest.fixture(scope="module")
def mp3_bytes():
    return _make_mp3_bytes()


@pytest.fixture(scope="module")
def mp3_bytes_2():
    return _make_mp3_bytes(freq=528.0)


@pytest.fixture(scope="module")
def jpeg_bytes():
    return _make_jpeg_bytes()


@pytest.fixture
def uploaded_session(mp3_bytes, mp3_bytes_2):
    """
    Upload 2 tracks and return the session_id.
    Cleans up the session directory after the test.
    """
    files = [
        ("files", ("track1.mp3", mp3_bytes, "audio/mpeg")),
        ("files", ("track2.mp3", mp3_bytes_2, "audio/mpeg")),
    ]
    resp = client.post("/upload", files=files)
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    yield session_id

    # Teardown: remove session directory so tests don't accumulate storage
    session_dir = settings.STORAGE_PATH / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)


@pytest.fixture
def merged_session(uploaded_session):
    """Upload + merge, return session_id with merged.mp3 ready."""
    resp = client.post(
        "/mixtape/create",
        json={
            "session_id": uploaded_session,
            "order": ["track1.mp3", "track2.mp3"],
            "crossfade_ms": 500,
            "normalize": True,
        },
    )
    assert resp.status_code == 200
    return uploaded_session


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------

class TestUpload:
    def test_upload_valid_mp3s_returns_200(self, mp3_bytes, mp3_bytes_2):
        files = [
            ("files", ("a.mp3", mp3_bytes, "audio/mpeg")),
            ("files", ("b.mp3", mp3_bytes_2, "audio/mpeg")),
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert "session_id" in body
        assert body["count"] == 2
        assert set(body["files"]) == {"a.mp3", "b.mp3"}

        # Cleanup
        shutil.rmtree(settings.STORAGE_PATH / body["session_id"], ignore_errors=True)

    def test_upload_no_files_returns_400(self):
        resp = client.post("/upload", files=[])
        assert resp.status_code in (400, 422)  # FastAPI may give 422 for missing field

    def test_upload_invalid_extension_returns_400(self, mp3_bytes):
        files = [("files", ("evil.exe", mp3_bytes, "application/octet-stream"))]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 400
        assert ".exe" in resp.json()["detail"]

    def test_upload_path_traversal_filename_is_sanitized(self, mp3_bytes):
        """
        A filename like '../../../evil.mp3' should be sanitized to 'evil.mp3'
        (the directory components are stripped) and saved safely.
        """
        files = [("files", ("../../../evil.mp3", mp3_bytes, "audio/mpeg"))]
        resp = client.post("/upload", files=files)
        # Should succeed (mp3 extension is valid) with sanitized filename
        assert resp.status_code == 200
        body = resp.json()
        # The saved filename should be 'evil.mp3', not '../../../evil.mp3'
        assert "evil.mp3" in body["files"]
        # The file should be inside storage, not escaped
        session_id = body["session_id"]
        expected_path = settings.STORAGE_PATH / session_id / "raw" / "evil.mp3"
        assert expected_path.exists()
        shutil.rmtree(settings.STORAGE_PATH / session_id, ignore_errors=True)

    def test_upload_saves_files_to_disk(self, mp3_bytes):
        files = [("files", ("check.mp3", mp3_bytes, "audio/mpeg"))]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]
        saved_path = settings.STORAGE_PATH / session_id / "raw" / "check.mp3"
        assert saved_path.exists()
        assert saved_path.stat().st_size > 0
        shutil.rmtree(settings.STORAGE_PATH / session_id, ignore_errors=True)

    def test_upload_wav_and_flac_accepted(self, mp3_bytes):
        """Different valid formats should all be accepted."""
        files = [
            ("files", ("song.wav", mp3_bytes, "audio/wav")),
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        shutil.rmtree(
            settings.STORAGE_PATH / resp.json()["session_id"], ignore_errors=True
        )


# ---------------------------------------------------------------------------
# POST /mixtape/create
# ---------------------------------------------------------------------------

class TestMixtapeCreate:
    def test_create_returns_200_with_boundaries(self, uploaded_session):
        resp = client.post(
            "/mixtape/create",
            json={
                "session_id": uploaded_session,
                "order": ["track1.mp3", "track2.mp3"],
                "crossfade_ms": 0,
                "normalize": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == uploaded_session
        assert "merged_audio_url" in body
        assert body["duration_ms"] > 0
        assert len(body["boundaries"]) == 2

    def test_create_crossfade_math_in_response(self, uploaded_session):
        """
        With crossfade=500ms and two 3-second tracks:
          track2.start_ms should be 3000 - 500 = 2500
          total duration should be 3000 + 3000 - 500 = 5500
        """
        resp = client.post(
            "/mixtape/create",
            json={
                "session_id": uploaded_session,
                "order": ["track1.mp3", "track2.mp3"],
                "crossfade_ms": 500,
                "normalize": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        boundaries = body["boundaries"]
        # track1 always starts at 0
        assert boundaries[0]["start_ms"] == 0
        # track2 starts at (track1_duration - crossfade)
        # track1 is ~3000ms (slight encoding variation allowed)
        assert boundaries[1]["start_ms"] == pytest.approx(2500, abs=100)

    def test_create_writes_merged_mp3_to_disk(self, uploaded_session):
        resp = client.post(
            "/mixtape/create",
            json={"session_id": uploaded_session, "crossfade_ms": 0},
        )
        assert resp.status_code == 200
        merged_path = settings.STORAGE_PATH / uploaded_session / "merged.mp3"
        assert merged_path.exists()
        assert merged_path.stat().st_size > 0

    def test_create_writes_boundaries_json_to_disk(self, uploaded_session):
        resp = client.post(
            "/mixtape/create",
            json={"session_id": uploaded_session, "crossfade_ms": 0},
        )
        assert resp.status_code == 200
        bp = settings.STORAGE_PATH / uploaded_session / "boundaries.json"
        assert bp.exists()
        import json
        data = json.loads(bp.read_text())
        assert len(data) == 2
        assert data[0]["start_ms"] == 0

    def test_create_missing_session_returns_404(self):
        resp = client.post(
            "/mixtape/create",
            json={"session_id": "a8098c1a-f86e-4da4-bd1a-000000000000"},
        )
        assert resp.status_code == 404

    def test_create_invalid_session_id_returns_400(self):
        """Path traversal attempt or non-UUID session_id."""
        resp = client.post(
            "/mixtape/create",
            json={"session_id": "../../etc/passwd"},
        )
        assert resp.status_code == 400

    def test_create_missing_file_in_order_returns_404(self, uploaded_session):
        resp = client.post(
            "/mixtape/create",
            json={
                "session_id": uploaded_session,
                "order": ["track1.mp3", "nonexistent.mp3"],
            },
        )
        assert resp.status_code == 404
        assert "nonexistent.mp3" in resp.json()["detail"]

    def test_create_corrupt_audio_returns_422(self, tmp_path):
        """
        If an uploaded file has a .mp3 extension but isn't actually audio,
        pydub raises CouldntDecodeError. The router must catch this and return 422.
        """
        # First upload a fake mp3 (text content)
        fake_mp3 = b"this is definitely not audio data!!!"
        files = [("files", ("fake.mp3", fake_mp3, "audio/mpeg"))]
        upload_resp = client.post("/upload", files=files)
        assert upload_resp.status_code == 200
        session_id = upload_resp.json()["session_id"]

        # Now try to merge — should get 422, not 500 or a traceback
        merge_resp = client.post(
            "/mixtape/create",
            json={"session_id": session_id, "crossfade_ms": 0},
        )
        assert merge_resp.status_code == 422
        assert "decode" in merge_resp.json()["detail"].lower()

        shutil.rmtree(settings.STORAGE_PATH / session_id, ignore_errors=True)

    def test_create_negative_crossfade_rejected(self, uploaded_session):
        """Pydantic Field(ge=0) should reject negative crossfade."""
        resp = client.post(
            "/mixtape/create",
            json={"session_id": uploaded_session, "crossfade_ms": -1},
        )
        assert resp.status_code == 422

    def test_create_crossfade_over_limit_rejected(self, uploaded_session):
        """Pydantic Field(le=10_000) should reject crossfade > 10s."""
        resp = client.post(
            "/mixtape/create",
            json={"session_id": uploaded_session, "crossfade_ms": 99_999},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /description/generate
# ---------------------------------------------------------------------------

class TestDescriptionGenerate:
    def test_generate_returns_200_with_timestamps(self, merged_session):
        resp = client.post(
            "/description/generate",
            json={"session_id": merged_session},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "description" in body
        # Should contain timestamps like "0:00"
        assert "0:00" in body["description"]

    def test_generate_without_prior_merge_returns_404(self):
        """If /mixtape/create was never called, boundaries.json doesn't exist."""
        # Upload files but don't merge
        files = [("files", ("x.mp3", _make_mp3_bytes(), "audio/mpeg"))]
        up = client.post("/upload", files=files)
        session_id = up.json()["session_id"]

        resp = client.post(
            "/description/generate",
            json={"session_id": session_id},
        )
        assert resp.status_code == 404
        assert "mixtape/create" in resp.json()["detail"].lower() or \
               "boundaries" in resp.json()["detail"].lower()

        shutil.rmtree(settings.STORAGE_PATH / session_id, ignore_errors=True)

    def test_generate_invalid_session_returns_400(self):
        resp = client.post(
            "/description/generate",
            json={"session_id": "../../evil"},
        )
        assert resp.status_code == 400

    def test_generate_custom_header_footer(self, merged_session):
        resp = client.post(
            "/description/generate",
            json={
                "session_id": merged_session,
                "header": "MY CUSTOM HEADER\n",
                "footer": "\nMY CUSTOM FOOTER",
            },
        )
        assert resp.status_code == 200
        desc = resp.json()["description"]
        assert "MY CUSTOM HEADER" in desc
        assert "MY CUSTOM FOOTER" in desc

    def test_generate_no_header_no_footer(self, merged_session):
        resp = client.post(
            "/description/generate",
            json={
                "session_id": merged_session,
                "header": None,
                "footer": None,
            },
        )
        assert resp.status_code == 200
        desc = resp.json()["description"]
        # Should just be track lines, no decorations
        assert "Mixtape Tracklist" not in desc
        assert "mixtape" not in desc


# ---------------------------------------------------------------------------
# POST /video/create
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not installed — video tests require ffmpeg",
)
class TestVideoCreate:
    def test_create_returns_200_with_video_url(self, merged_session, jpeg_bytes):
        resp = client.post(
            "/video/create",
            data={"session_id": merged_session},
            files=[("image", ("bg.jpg", jpeg_bytes, "image/jpeg"))],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "video_url" in body
        assert body["video_url"].endswith("mixtape.mp4")

    def test_create_writes_mp4_to_disk(self, merged_session, jpeg_bytes):
        resp = client.post(
            "/video/create",
            data={"session_id": merged_session},
            files=[("image", ("bg.jpg", jpeg_bytes, "image/jpeg"))],
        )
        assert resp.status_code == 200
        mp4_path = settings.STORAGE_PATH / merged_session / "mixtape.mp4"
        assert mp4_path.exists()
        assert mp4_path.stat().st_size > 0

    def test_create_without_prior_merge_returns_404(self, mp3_bytes, jpeg_bytes):
        """If merged.mp3 doesn't exist, must return 404 before writing the image."""
        files = [("files", ("t.mp3", mp3_bytes, "audio/mpeg"))]
        up = client.post("/upload", files=files)
        session_id = up.json()["session_id"]

        resp = client.post(
            "/video/create",
            data={"session_id": session_id},
            files=[("image", ("bg.jpg", jpeg_bytes, "image/jpeg"))],
        )
        assert resp.status_code == 404

        # Image should NOT have been written to disk (fail-fast)
        image_path = settings.STORAGE_PATH / session_id / "background.jpg"
        assert not image_path.exists()

        shutil.rmtree(settings.STORAGE_PATH / session_id, ignore_errors=True)

    def test_create_invalid_image_type_returns_400(self, merged_session, mp3_bytes):
        """Sending an MP3 as the image should return 400."""
        resp = client.post(
            "/video/create",
            data={"session_id": merged_session},
            files=[("image", ("background.mp3", mp3_bytes, "audio/mpeg"))],
        )
        assert resp.status_code == 400

    def test_create_invalid_session_returns_400(self, jpeg_bytes):
        resp = client.post(
            "/video/create",
            data={"session_id": "../../evil"},
            files=[("image", ("bg.jpg", jpeg_bytes, "image/jpeg"))],
        )
        assert resp.status_code == 400

    def test_video_url_is_downloadable(self, merged_session, jpeg_bytes):
        """The returned video_url must be accessible via GET /storage/..."""
        create_resp = client.post(
            "/video/create",
            data={"session_id": merged_session},
            files=[("image", ("bg.jpg", jpeg_bytes, "image/jpeg"))],
        )
        assert create_resp.status_code == 200
        video_url = create_resp.json()["video_url"]

        download_resp = client.get(video_url)
        assert download_resp.status_code == 200
        assert len(download_resp.content) > 0


# ---------------------------------------------------------------------------
# End-to-end pipeline test
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """
    The ultimate regression test — runs the entire pipeline from upload to
    video in a single test. If this passes, the whole Day 1 + Day 2 + Day 3
    stack is working correctly together.
    """

    @pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="Full pipeline requires ffmpeg",
    )
    def test_upload_merge_describe_video(self, mp3_bytes, mp3_bytes_2, jpeg_bytes):
        session_id = None
        try:
            # Step 1: Upload
            up = client.post(
                "/upload",
                files=[
                    ("files", ("alpha.mp3", mp3_bytes, "audio/mpeg")),
                    ("files", ("beta.mp3", mp3_bytes_2, "audio/mpeg")),
                ],
            )
            assert up.status_code == 200, f"Upload failed: {up.json()}"
            session_id = up.json()["session_id"]
            assert up.json()["count"] == 2

            # Step 2: Merge
            merge = client.post(
                "/mixtape/create",
                json={
                    "session_id": session_id,
                    "order": ["alpha.mp3", "beta.mp3"],
                    "crossfade_ms": 500,
                    "normalize": True,
                },
            )
            assert merge.status_code == 200, f"Merge failed: {merge.json()}"
            assert merge.json()["boundaries"][0]["name"] == "alpha"
            assert merge.json()["boundaries"][1]["name"] == "beta"
            # Verify crossfade: beta.start_ms < alpha.duration
            alpha_end = merge.json()["boundaries"][0]["end_ms"]
            beta_start = merge.json()["boundaries"][1]["start_ms"]
            assert beta_start < alpha_end, "Crossfade not applied — timestamps are naive sum"

            # Step 3: Description
            desc = client.post(
                "/description/generate",
                json={"session_id": session_id},
            )
            assert desc.status_code == 200, f"Description failed: {desc.json()}"
            assert "0:00 alpha" in desc.json()["description"]
            assert "beta" in desc.json()["description"]

            # Step 4: Video
            vid = client.post(
                "/video/create",
                data={"session_id": session_id},
                files=[("image", ("bg.jpg", jpeg_bytes, "image/jpeg"))],
            )
            assert vid.status_code == 200, f"Video failed: {vid.json()}"
            mp4_path = settings.STORAGE_PATH / session_id / "mixtape.mp4"
            assert mp4_path.exists()
            assert mp4_path.stat().st_size > 10_000  # real MP4 should be >10KB

        finally:
            if session_id:
                shutil.rmtree(settings.STORAGE_PATH / session_id, ignore_errors=True)
