"""
frontend/app.py
----------------
Streamlit UI for the YouTube Mixtape Generator.

Robustness improvements (Day 3):
---------------------------------
1. Backend connectivity check at startup — shows clear error if API is down
2. All requests wrapped in try/except for ConnectionError and HTTPError
3. Timeout set on every request (avoids hanging forever)
4. File count validation before sending (client-side fast rejection)
5. Progress indicators on long operations (merge, video)
6. Audio preview plays bytes directly (works without StaticFiles URL)
7. Session state is preserved across Streamlit reruns

4-step flow:
  Step 1 → Upload audio files       → session_id is born
  Step 2 → Configure & merge        → merged.mp3 + boundaries.json
  Step 3 → Generate description      → copy-paste-ready text
  Step 4 → Create video + download   → mixtape.mp4
"""

from __future__ import annotations

import time
import requests
import streamlit as st

BACKEND_URL = "http://localhost:8000"
REQUEST_TIMEOUT = 180  # seconds — video creation can take up to 3 min


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="YouTube Mixtape Generator",
    page_icon="🎵",
    layout="wide",
)

st.title("🎵 YouTube Mixtape Generator")
st.markdown("Upload audio tracks → Merge with crossfade → Generate timestamps → Export MP4")


# ---------------------------------------------------------------------------
# Backend connectivity check
# ---------------------------------------------------------------------------

def check_backend() -> bool:
    """Return True if the FastAPI backend is reachable."""
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
    except requests.exceptions.Timeout:
        return False


if not check_backend():
    st.error(
        "⚠️ **Cannot connect to backend API.**\n\n"
        "Start it in a separate terminal:\n"
        "```bash\n"
        "uv run uvicorn backend.main:app --reload --port 8000\n"
        "```"
    )
    st.stop()


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
# st.session_state persists across Streamlit reruns (every button click
# causes the whole script to rerun from the top — session_state is the
# only way to remember things between reruns).

if "session_id" not in st.session_state:
    st.session_state.session_id = None          # UUID4 from /upload
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []        # list of filenames
if "boundaries" not in st.session_state:
    st.session_state.boundaries = []            # from /mixtape/create
if "merged_audio_bytes" not in st.session_state:
    st.session_state.merged_audio_bytes = None  # for st.audio preview
if "description" not in st.session_state:
    st.session_state.description = ""           # from /description/generate
if "video_bytes" not in st.session_state:
    st.session_state.video_bytes = None         # for st.video + download


# ---------------------------------------------------------------------------
# Helper: safe API call
# ---------------------------------------------------------------------------

def api_post(endpoint: str, **kwargs) -> requests.Response | None:
    """
    POST to backend with timeout and error handling.
    Returns the Response on success, None on connection failure.
    Shows st.error() on HTTP error or connection error.
    """
    url = f"{BACKEND_URL}{endpoint}"
    try:
        resp = requests.post(url, timeout=REQUEST_TIMEOUT, **kwargs)
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            st.error(f"❌ API Error {resp.status_code}: {detail}")
            return None
        return resp
    except requests.exceptions.ConnectionError:
        st.error("❌ Lost connection to backend. Is it still running?")
        return None
    except requests.exceptions.Timeout:
        st.error(f"❌ Request timed out after {REQUEST_TIMEOUT}s.")
        return None


# ---------------------------------------------------------------------------
# STEP 1: Upload Audio Files
# ---------------------------------------------------------------------------

st.header("Step 1 — Upload Audio Files")

with st.expander("📁 Upload Files", expanded=st.session_state.session_id is None):
    uploaded = st.file_uploader(
        "Choose audio files (MP3, WAV, FLAC, OGG, M4A, AAC)",
        accept_multiple_files=True,
        type=["mp3", "wav", "flac", "ogg", "m4a", "aac"],
        key="file_uploader",
    )

    if uploaded:
        st.write(f"**{len(uploaded)} file(s) selected:**")
        for f in uploaded:
            size_kb = len(f.getvalue()) / 1024
            st.write(f"  • {f.name} ({size_kb:.1f} KB)")

    col1, col2 = st.columns([1, 4])
    with col1:
        upload_btn = st.button("⬆️ Upload", disabled=not uploaded)

    if upload_btn and uploaded:
        if len(uploaded) < 1:
            st.warning("Please select at least 1 audio file.")
        else:
            files_payload = [
                ("files", (f.name, f.getvalue(), f.type or "audio/mpeg"))
                for f in uploaded
            ]
            with st.spinner(f"Uploading {len(uploaded)} file(s)..."):
                resp = api_post("/upload", files=files_payload)

            if resp:
                body = resp.json()
                st.session_state.session_id = body["session_id"]
                st.session_state.uploaded_files = body["files"]
                # Reset downstream state when new files are uploaded
                st.session_state.boundaries = []
                st.session_state.merged_audio_bytes = None
                st.session_state.description = ""
                st.session_state.video_bytes = None
                st.success(
                    f"✅ Uploaded {body['count']} file(s). "
                    f"Session: `{body['session_id'][:8]}...`"
                )

if st.session_state.session_id:
    st.info(f"🗂️ Active session: `{st.session_state.session_id[:8]}...` | "
            f"Files: {', '.join(st.session_state.uploaded_files)}")

st.divider()


# ---------------------------------------------------------------------------
# STEP 2: Configure & Merge
# ---------------------------------------------------------------------------

st.header("Step 2 — Configure & Merge Tracks")

if not st.session_state.session_id:
    st.warning("Complete Step 1 first (upload files).")
else:
    with st.expander("⚙️ Merge Settings", expanded=not st.session_state.boundaries):
        files = st.session_state.uploaded_files

        st.subheader("Track Order")
        st.markdown("Drag names below or leave as-is for alphabetical order.")

        # Display the current order (user can note the order they want)
        for i, fname in enumerate(files, 1):
            st.write(f"  **{i}.** {fname}")

        # Custom order input
        order_input = st.text_area(
            "Custom order (one filename per line, leave empty for alphabetical):",
            value="\n".join(files),
            height=120,
            help="Edit the order here. Each line = one track. Must match uploaded filenames exactly.",
        )

        st.subheader("Crossfade")
        crossfade_ms = st.slider(
            "Crossfade duration (ms)",
            min_value=0,
            max_value=5_000,
            value=2_000,
            step=100,
            help=(
                "How long (in milliseconds) the end of one track overlaps "
                "with the start of the next. 0 = hard cut. 2000 = 2-second fade."
            ),
        )
        # Show crossfade in human-readable form
        st.caption(f"= {crossfade_ms / 1000:.1f} seconds overlap between tracks")

        normalize = st.checkbox(
            "Normalize volume (recommended)",
            value=True,
            help=(
                "Adjusts each track to -14 dBFS RMS — the Spotify/YouTube standard. "
                "Prevents jarring volume jumps between tracks."
            ),
        )

        merge_btn = st.button("🎵 Merge Tracks")

    if merge_btn:
        custom_order = [
            line.strip() for line in order_input.splitlines() if line.strip()
        ]
        payload = {
            "session_id": st.session_state.session_id,
            "order": custom_order,
            "crossfade_ms": crossfade_ms,
            "normalize": normalize,
        }
        with st.spinner("Merging tracks... (this may take 30–60 seconds for long files)"):
            resp = api_post("/mixtape/create", json=payload)

        if resp:
            body = resp.json()
            st.session_state.boundaries = body["boundaries"]

            # Fetch the merged audio for preview
            audio_url = f"{BACKEND_URL}{body['merged_audio_url']}"
            try:
                audio_resp = requests.get(audio_url, timeout=60)
                if audio_resp.ok:
                    st.session_state.merged_audio_bytes = audio_resp.content
            except Exception:
                pass  # Preview is optional — don't fail the whole step

            duration_sec = body["duration_ms"] / 1000
            mins = int(duration_sec // 60)
            secs = int(duration_sec % 60)
            st.success(f"✅ Merged! Total duration: {mins}:{secs:02d}")

    if st.session_state.boundaries:
        st.subheader("📋 Track Boundaries")
        for b in st.session_state.boundaries:
            ms = b["start_ms"]
            total_s = ms // 1000
            mins = total_s // 60
            secs = total_s % 60
            timestamp = f"{mins}:{secs:02d}" if mins < 60 else f"{mins//60}:{mins%60:02d}:{secs:02d}"
            st.write(f"  `{timestamp}` — **{b['name']}**")

    if st.session_state.merged_audio_bytes:
        st.subheader("🔊 Preview")
        st.audio(st.session_state.merged_audio_bytes, format="audio/mp3")

st.divider()


# ---------------------------------------------------------------------------
# STEP 3: Generate YouTube Description
# ---------------------------------------------------------------------------

st.header("Step 3 — Generate YouTube Description")

if not st.session_state.boundaries:
    st.warning("Complete Step 2 first (merge tracks).")
else:
    with st.expander("📝 Description Settings", expanded=not st.session_state.description):
        header = st.text_area(
            "Header text (appears before timestamps):",
            value="🎵 Mixtape Tracklist\n",
            height=70,
        )
        footer = st.text_area(
            "Footer text (appears after timestamps):",
            value="\n\n#mixtape #music",
            height=70,
        )
        desc_btn = st.button("📝 Generate Description")

    if desc_btn:
        payload = {
            "session_id": st.session_state.session_id,
            "header": header or None,
            "footer": footer or None,
        }
        with st.spinner("Generating description..."):
            resp = api_post("/description/generate", json=payload)

        if resp:
            st.session_state.description = resp.json()["description"]
            st.success("✅ Description generated!")

    if st.session_state.description:
        st.subheader("📋 Your YouTube Description")
        st.markdown(
            "_Click inside the box, Ctrl+A to select all, Ctrl+C to copy:_"
        )
        st.text_area(
            "description_output",
            value=st.session_state.description,
            height=200,
            label_visibility="collapsed",
        )
        st.download_button(
            "⬇️ Download as .txt",
            data=st.session_state.description.encode("utf-8"),
            file_name="youtube_description.txt",
            mime="text/plain",
        )

st.divider()


# ---------------------------------------------------------------------------
# STEP 4: Create Video
# ---------------------------------------------------------------------------

st.header("Step 4 — Create YouTube Video")

if not st.session_state.boundaries:
    st.warning("Complete Step 2 first (merge tracks).")
else:
    with st.expander("🎬 Video Settings", expanded=st.session_state.video_bytes is None):
        bg_image = st.file_uploader(
            "Background image (JPEG or PNG, 1920×1080 recommended):",
            type=["jpg", "jpeg", "png"],
            key="bg_image_uploader",
        )

        if bg_image:
            st.image(bg_image, caption="Preview", use_container_width=True)

        st.info(
            "💡 **Tip:** Use a 1920×1080 (Full HD) image. "
            "YouTube recommends this resolution for best quality."
        )

        video_btn = st.button("🎬 Create Video", disabled=not bg_image)

    if video_btn and bg_image:
        files_payload = [
            ("image", (bg_image.name, bg_image.getvalue(), bg_image.type or "image/jpeg"))
        ]
        form_data = {"session_id": st.session_state.session_id}

        with st.spinner(
            "Creating MP4 video... (ffmpeg is running — may take 30–120 seconds for long mixes)"
        ):
            resp = api_post("/video/create", data=form_data, files=files_payload)

        if resp:
            video_url = f"{BACKEND_URL}{resp.json()['video_url']}"
            try:
                with st.spinner("Downloading video for preview..."):
                    video_resp = requests.get(video_url, timeout=120)
                    if video_resp.ok:
                        st.session_state.video_bytes = video_resp.content
            except Exception as e:
                st.warning(f"Video created but preview failed: {e}")

            st.success("✅ Video created!")

    if st.session_state.video_bytes:
        st.subheader("🎬 Your Video")
        st.video(st.session_state.video_bytes)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Download MP4",
                data=st.session_state.video_bytes,
                file_name="mixtape.mp4",
                mime="video/mp4",
                use_container_width=True,
            )
        with col2:
            st.info("🚀 Upload this file to YouTube Studio directly!")

st.divider()


# ---------------------------------------------------------------------------
# Sidebar — session info and reset
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📊 Session Info")

    if st.session_state.session_id:
        st.success("🟢 Session Active")
        st.code(st.session_state.session_id, language=None)

        if st.session_state.uploaded_files:
            st.write(f"**Files uploaded:** {len(st.session_state.uploaded_files)}")
            for f in st.session_state.uploaded_files:
                st.write(f"  • {f}")

        if st.session_state.boundaries:
            st.write(f"**Tracks merged:** {len(st.session_state.boundaries)}")

        if st.session_state.description:
            st.write("**Description:** ✅ Generated")

        if st.session_state.video_bytes:
            size_mb = len(st.session_state.video_bytes) / (1024 * 1024)
            st.write(f"**Video:** ✅ {size_mb:.1f} MB")
    else:
        st.warning("🔴 No active session")

    st.divider()

    if st.button("🔄 Start Over (New Session)", use_container_width=True):
        # Clear all session state to start fresh
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.divider()
    st.caption(
        "**API:** http://localhost:8000  \n"
        "**Docs:** [Swagger UI](http://localhost:8000/docs)  \n"
        "**Backend:** FastAPI + pydub + ffmpeg"
    )
