# YouTube Mixtape Generator

> Drop in a folder of audio tracks — get back a merged audio file, a YouTube-ready description with clickable timestamps, and an uploadable MP4 video. No manual editing, no timeline scrubbing. The whole pipeline runs in one click.

---

<!-- DEMO_VIDEO_LINK -->
[![Demo](https://img.shields.io/badge/▶_Watch_Demo-blue?style=for-the-badge)](https://github.com/sidd1507/youtube-mixtape-generator/releases/tag/v1.0)

---

## ✨ Features

- **Multi-format audio upload** — MP3, WAV, FLAC, OGG, M4A, AAC; drag-and-drop via Streamlit or multipart POST
- **Crossfade merging** — smooth Pydub-powered overlap with mathematically correct boundary timestamps (no cumulative drift)
- **Loudness normalisation** — optional per-track gain levelling before merge
- **Auto YouTube description** — timestamped tracklist with custom header/footer, copy-paste ready
- **Audio → Video conversion** — static background image + merged audio → H.264/AAC MP4 via FFmpeg (no moviepy)
- **Session isolation** — every run gets its own UUID4 session; concurrent users never collide
- **FastAPI REST backend** — clean JSON API, fully documented at `/docs`
- **Streamlit frontend** — thin client, zero business logic in the UI layer
- **166 tests, 0 failures** — unit tests, API integration tests, security/adversarial tests, real end-to-end pipeline test with ffprobe verification

---

## Architecture

```
Raw Audio Files
      │
      ▼
┌─────────────┐   POST /upload    ┌──────────────────────────┐
│  Streamlit  │ ───────────────►  │   FastAPI Backend         │
│  Frontend   │                   │                           │
│  :8501      │ ◄─────────────── │  /upload   → storage/     │
│             │   session_id      │  /mixtape  → merged.mp3   │
│             │                   │  /description → text      │
│             │                   │  /video    → mixtape.mp4  │
└─────────────┘                   └──────────────────────────┘
                                             │
                          ┌──────────────────┼──────────────────┐
                          ▼                  ▼                  ▼
                   audio_engine      description_engine    video_engine
                   (Pydub merge,     (timestamp math,      (FFmpeg subprocess
                    crossfade,        header/footer         image+audio→MP4)
                    normalise)        template)
                          │                  │                  │
                          └──────────────────┴──────────────────┘
                                             │
                                             ▼
                              YouTube-ready output:
                              merged.mp3 + description.txt + mixtape.mp4
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.12 | Type hints, f-strings, `match` |
| Package manager | [uv](https://github.com/astral-sh/uv) | Deterministic, fast, pyproject.toml-native |
| REST API | FastAPI 0.111 | Auto-docs, Pydantic validation, async-ready |
| Frontend | Streamlit 1.36 | Thin client; no state machine needed |
| Audio processing | Pydub 0.25 | AudioSegment crossfade + boundary math |
| Video encoding | FFmpeg (subprocess) | Native H.264/AAC, 10× faster than moviepy for static image |
| Testing | pytest 8 | 166 tests: unit, API, security, real E2E pipeline |

---

## Project Structure

```
youtube-mixtape-generator/
├── backend/
│   ├── main.py                   # FastAPI app, CORS, routers, /health
│   ├── core/
│   │   ├── config.py             # Settings (STORAGE_PATH, HOST, PORT)
│   │   └── security.py          # UUID4 validation, safe_filename()
│   ├── routers/
│   │   ├── upload.py             # POST /upload
│   │   ├── mixtape.py            # POST /mixtape/create
│   │   ├── description.py        # POST /description/generate
│   │   └── video.py              # POST /video/create
│   ├── services/
│   │   ├── audio_engine.py       # merge_tracks(), normalize_track(), load_boundaries()
│   │   ├── description_engine.py # format_timestamp(), generate_description()
│   │   └── video_engine.py       # image_audio_to_video() via ffmpeg subprocess
│   ├── schemas/
│   │   └── models.py             # Pydantic request/response models
│   └── storage/                  # ← created at runtime, gitignored
│       └── {session_id}/
│           ├── raw/              # uploaded tracks
│           ├── merged.mp3
│           ├── boundaries.json
│           └── mixtape.mp4
├── frontend/
│   ├── app.py                    # Single-page Streamlit UI
│   ├── api_client.py             # Thin requests wrapper (no business logic)
│   └── config.py                 # BACKEND_URL, timeouts
├── tests/
│   ├── test_audio_engine.py      # Crossfade math, silence guard, normalization
│   ├── test_description_engine.py# Timestamp format, header/footer, edge cases
│   ├── test_video_engine.py      # FFmpeg integration tests
│   ├── test_api.py               # Full HTTP integration tests (TestClient)
│   ├── test_edge_cases.py        # Boundary conditions, unicode, silence
│   ├── test_hidden_security.py   # Path traversal, XSS, session isolation, concurrency
│   └── test_real_pipeline.py     # Real E2E: ffmpeg audio → merge → video → ffprobe verify
├── sample_assets/
│   ├── track1.mp3                # ~40KB sine tone (safe for git)
│   ├── track2.mp3                # ~40KB sine tone
│   ├── track3.mp3                # ~40KB sine tone
│   └── bg.jpg                    # Background image for video demo
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites

**1. Install uv** (Python package manager)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**2. Install FFmpeg** (required for video encoding)

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows — download from https://ffmpeg.org/download.html
# or: winget install ffmpeg
```

**3. Verify FFmpeg is on PATH**

```bash
ffmpeg -version   # should print version 4.x or later
```

---

### Install & Run

```bash
# 1. Clone
git clone https://github.com/sidd1507/youtube-mixtape-generator.git
cd youtube-mixtape-generator

# 2. Create virtualenv and install all dependencies
uv venv
uv sync

# 3. Copy environment config (defaults work out of the box)
cp .env.example .env

# 4. Start the backend (terminal 1)
uv run uvicorn backend.main:app --reload --port 8000

# 5. Start the frontend (terminal 2)
uv run streamlit run frontend/app.py

# 6. Open the app
open http://localhost:8501
# API docs at: http://localhost:8000/docs
```

> **Python version:** 3.11 or 3.12 required. Python 3.13+ removed `audioop` which Pydub depends on. The `.python-version` file pins 3.12 if you use pyenv.

---

## Usage

1. **Upload tracks** — drag and drop 1–10 audio files (MP3, WAV, FLAC, OGG, M4A, AAC). A session ID is created automatically.
2. **Set order** — drag to reorder the track list. Default is alphabetical.
3. **Set crossfade** — choose 0–10,000ms overlap between tracks. Default 2,000ms.
4. **Generate Mixtape** — click to merge. Shows total duration + clickable boundaries.
5. **Generate Description** — optionally edit the header/footer. Click to generate the timestamped YouTube description. Copy and paste directly into YouTube Studio.
6. **Upload background image** — JPEG or PNG, any resolution (auto-resized). Required for video.
7. **Generate Video** — encodes the merged audio + background image into a 1920×1080 H.264 MP4.
8. **Download** — download the final MP4 and/or the description as `.txt`.

---

## API Reference

All endpoints are also available at **`http://localhost:8000/docs`** (Swagger UI).

### `POST /upload`

Upload one or more audio files. Creates a new session.

| Field | Type | Notes |
|---|---|---|
| `files` | `multipart/form-data` | 1–10 files; `.mp3 .wav .flac .ogg .m4a .aac` |

**Response**
```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "files": ["track1.mp3", "track2.mp3"],
  "count": 2
}
```

---

### `POST /mixtape/create`

Merge uploaded tracks with optional crossfade and normalisation.

```json
{
  "session_id": "3fa85f64-...",
  "order": ["track2.mp3", "track1.mp3"],
  "crossfade_ms": 2000,
  "normalize": true
}
```

**Response**
```json
{
  "session_id": "3fa85f64-...",
  "merged_url": "/storage/3fa85f64-.../merged.mp3",
  "duration_ms": 347000,
  "boundaries": [
    {"name": "track2", "start_ms": 0, "end_ms": 180000},
    {"name": "track1", "start_ms": 178000, "end_ms": 347000}
  ]
}
```

> **Boundary math:** `start_ms = len(merged_so_far) - crossfade_ms` — computed incrementally, not from a cumulative sum, so timestamps stay accurate regardless of crossfade length.

---

### `POST /description/generate`

Generate a timestamped YouTube description from saved boundaries.

```json
{
  "session_id": "3fa85f64-...",
  "header": "🎵 My Playlist\n",
  "footer": "\n\n#music #mixtape"
}
```

**Response**
```json
{
  "session_id": "3fa85f64-...",
  "description": "🎵 My Playlist\n\n0:00 track2\n2:58 track1\n\n#music #mixtape"
}
```

---

### `POST /video/create`

Combine the merged audio with a background image to produce a YouTube-ready MP4.

| Field | Type | Notes |
|---|---|---|
| `session_id` | `form field` | Must have a completed mixtape |
| `image` | `multipart/form-data` | JPEG or PNG background |

**Response**
```json
{
  "session_id": "3fa85f64-...",
  "video_url": "/storage/3fa85f64-.../mixtape.mp4"
}
```

**Video specs:** H.264, AAC 192kbps, 1920×1080 (image is padded/scaled to fit), duration matches merged audio exactly.

---

### `GET /health`

```json
{"status": "ok", "storage": "backend/storage"}
```

---

## Testing

```bash
# Run all 166 tests
uv run pytest tests/ -v

# Quick pass/fail summary only
uv run pytest tests/ -q

# Run a single file
uv run pytest tests/test_audio_engine.py -v

# Run only the real end-to-end pipeline (requires ffmpeg)
uv run pytest tests/test_real_pipeline.py -v -s
```

**Test coverage by file:**

| File | Tests | What it covers |
|---|---|---|
| `test_audio_engine.py` | 37 | Crossfade math, silence guard, normalization, boundary accuracy |
| `test_description_engine.py` | 15 | Timestamp formatting, header/footer, unicode, edge cases |
| `test_video_engine.py` | 5 | FFmpeg integration, missing-file errors |
| `test_api.py` | 29 | HTTP integration: all endpoints, status codes, file validation |
| `test_edge_cases.py` | 38 | Silence tracks, 100-track lists, unicode filenames |
| `test_hidden_security.py` | 46 | Path traversal, XSS, fake audio files, session isolation, concurrency |
| `test_real_pipeline.py` | 16 | Real ffmpeg audio → merge → video → ffprobe structural verification |
| **Total** | **186** | **0 failures · 0 skips** |

---

## Known Limitations

- **Synchronous processing only** — long audio files (>1 hour) will block the request. No background task queue (Celery, RQ) is wired up. For production, wrap `merge_tracks()` in a FastAPI `BackgroundTask` or offload to a worker.
- **Local storage only** — files live in `backend/storage/{session_id}/` on the server filesystem. No S3, GCS, or cloud storage integration yet.
- **No authentication** — any client with the session UUID can access the files. Fine for local/personal use; add an API key or OAuth layer before exposing publicly.
- **No session TTL / cleanup** — old sessions accumulate in `storage/` indefinitely. Add a cron job or startup hook to prune directories older than N days.
- **FFmpeg must be installed system-wide** — the video encoder calls `ffmpeg` via `subprocess`. There is no bundled binary.

---

## License

MIT © 2026

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
