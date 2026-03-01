# AI Music App — Design Document
_Date: 2026-03-01_

---

## Requirements (Original Ask)

> Build a personal AI-assisted music tool with a clean frontend/backend separation (Python frontend for now, web portal later). The app should let me sing through a microphone and generate a clean audio track that matches my melody and rhythm — timbre doesn't matter, a default instrument is fine. I should also be able to upload an audio file (mp3 or common formats) and get the same result. I want to freely edit pitch and timing of any section, select a time range for playback, and — the key feature — select a segment, write a text prompt, and have AI modify that part. The AI-modified version should be audible alongside the original for easy comparison. Three distinct modification modes: style transfer, melody variation, and accompaniment generation. The AI context should include music before and after the selected segment so the result fits naturally into the full track. The system should support both a local GPU model and a cloud API, switchable from the UI. Budget is tight — prefer free or near-free tools. Code should be clean, modular, TDD-driven, with files kept short. The design should also think through good AI developer tooling for the project itself.

---

## Architecture

**Pattern:** FastAPI backend + Streamlit frontend (separate processes).

- `backend/` — all audio logic, MIDI processing, AI providers, REST API. Zero UI imports.
- `frontend/` — thin Streamlit client. Zero audio logic. Calls backend via `api_client.py`.
- Swapping to a React/web frontend later = replace `frontend/` only. Backend untouched.

**Runtime:** Both processes run in WSL2. Streamlit serves a local web page accessed from the Windows browser. Mic input and audio playback go through the browser's Web Audio API — no WSL2 audio bridge needed.

---

## Directory Structure

```
ai-music/
├── backend/
│   ├── main.py                    # FastAPI app, route registration
│   ├── config.py                  # StaticConfig (ports, paths, model settings)
│   ├── api/
│   │   └── routes/
│   │       ├── audio.py           # upload, record, waveform, export
│   │       ├── midi.py            # extract, get notes, edit notes, synthesize
│   │       └── ai.py              # modify, job status, compare
│   ├── services/
│   │   ├── audio_service.py       # format conversion, waveform extraction
│   │   ├── midi_service.py        # Basic Pitch extraction, FluidSynth render
│   │   ├── edit_service.py        # pitch/timing mutation on MIDI note events
│   │   └── ai_service.py          # context assembly, provider dispatch
│   ├── providers/
│   │   ├── base.py                # AIProvider abstract base class
│   │   ├── musicgen.py            # local MusicGen (GPU) implementation
│   │   └── replicate_provider.py  # Replicate API implementation
│   ├── repositories/
│   │   ├── base.py                # Abstract repository interfaces
│   │   └── file_repo.py           # File-based storage (Phase 1)
│   └── models/
│       └── schemas.py             # Pydantic models (DB-ready: UUID, timestamps)
├── frontend/
│   ├── app.py                     # Streamlit entry point, tab routing
│   ├── pages/
│   │   ├── record.py              # browser mic recording tab
│   │   ├── upload.py              # file upload tab
│   │   ├── editor.py              # waveform view + region select + note edit
│   │   └── ai_modify.py           # mode select, prompt input, compare toggle
│   └── api_client.py              # typed HTTP client for all backend calls
├── tests/
│   ├── backend/
│   │   ├── test_audio_service.py
│   │   ├── test_midi_service.py
│   │   ├── test_edit_service.py
│   │   ├── test_ai_service.py
│   │   └── test_routes.py
│   ├── fixtures/
│   │   ├── sample.wav             # 3-second sine wave test fixture
│   │   └── sample.mid             # minimal MIDI test fixture
│   └── conftest.py                # shared fixtures, mock providers
├── scripts/
│   ├── ctl                        # control: start/stop/restart/status/test
│   └── run_integration_test.sh    # upload → extract → synthesize → verify
├── assets/
│   └── soundfonts/
│       └── GeneralUser.sf2        # free General MIDI soundfont
├── docs/
│   └── plans/
│       └── 2026-03-01-ai-music-design.md
├── logs/
│   ├── backend.log
│   └── frontend.log
├── pyproject.toml
└── README.md
```

---

## Data Flow

```
[browser mic / audio file upload]
        │
        ▼
POST /audio/upload  or  /audio/record
        │  returns track_id (UUID)
        ▼
POST /midi/{track_id}/extract        ← Basic Pitch → .mid file + note events
        │  returns [Note]
        ▼
GET  /audio/{track_id}/playback      ← FluidSynth renders .mid → .wav → streams audio
        │
        ▼  (user selects a note or region and edits)
PUT  /midi/{track_id}/notes/{id}     ← mutate pitch/timing
POST /midi/{track_id}/synthesize     ← re-render .wav
        │
        ▼  (user requests AI modification)
POST /ai/{track_id}/modify           ← { mode, prompt, start_sec, end_sec, provider }
        │  returns job_id (async)
GET  /ai/jobs/{job_id}               ← poll: pending → running → done
GET  /ai/{track_id}/compare          ← original segment + AI segment for toggle
```

---

## API Contracts

| Method | Endpoint | Input | Output |
|--------|----------|-------|--------|
| POST | `/audio/upload` | multipart file (mp3/wav/m4a/flac) | `{ track_id, duration_sec, sample_rate }` |
| POST | `/audio/record` | multipart audio blob | `{ track_id, duration_sec, sample_rate }` |
| GET  | `/audio/{id}/waveform` | — | `{ times: [float], amplitudes: [float] }` |
| GET  | `/audio/{id}/playback` | — | audio stream (WAV) |
| POST | `/midi/{id}/extract` | — | `{ notes: [Note] }` |
| GET  | `/midi/{id}` | — | `{ notes: [Note] }` |
| PUT  | `/midi/{id}/notes/{note_id}` | `{ pitch_midi?, start_sec?, end_sec? }` | updated `Note` |
| POST | `/midi/{id}/synthesize` | — | `{ playback_url }` |
| POST | `/ai/{id}/modify` | `{ mode, prompt, start_sec, end_sec, provider }` | `{ job_id }` |
| GET  | `/ai/jobs/{job_id}` | — | `{ status, result_url? }` |
| GET  | `/ai/{id}/compare` | — | `{ original_url, modified_url }` |

---

## Data Models (DB-Ready)

All models use UUID primary keys and UTC timestamps. Designed to map 1:1 to Supabase tables when migrating from file-based storage.

```python
class Track(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    duration_sec: float
    sample_rate: int
    status: Literal["uploading", "ready", "processing"]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Note(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    pitch_midi: int        # 0–127
    start_sec: float
    end_sec: float
    velocity: int          # 0–127

class AIJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    mode: Literal["style", "melody", "accompaniment"]
    prompt: str
    provider: Literal["local", "replicate"]
    start_sec: float
    end_sec: float
    status: Literal["pending", "running", "done", "failed"]
    result_path: str | None = None
    error_msg: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

**Future Supabase tables:** `tracks`, `notes`, `ai_jobs` — columns match model fields exactly.

**Repository pattern** (swap storage by replacing one file):
```python
# repositories/base.py — abstract interface
class TrackRepository(ABC):
    async def save(self, track: Track) -> Track: ...
    async def get(self, track_id: UUID) -> Track: ...

# repositories/file_repo.py  ← Phase 1 (JSON files on disk, keyed by UUID)
# repositories/supabase_repo.py  ← Future drop-in replacement
```

---

## AI Provider Abstraction

```python
# providers/base.py
class AIProvider(ABC):
    @abstractmethod
    async def modify(
        self,
        before_audio: bytes,   # up to 10s of context before the segment
        segment_audio: bytes,  # the target segment to modify
        after_audio: bytes,    # up to 10s of context after the segment
        mode: Literal["style", "melody", "accompaniment"],
        prompt: str,
    ) -> bytes: ...            # returns modified segment audio (WAV bytes)
```

- `MusicGenProvider` — loads `facebook/musicgen-small` via HuggingFace `transformers`, runs on local GPU
- `ReplicateProvider` — calls Replicate API (~$0.07/run), no local GPU needed
- Streamlit sidebar toggle sends `provider: "local"` or `provider: "replicate"` in request body
- `ai_service.py` selects provider; no config file change needed to switch

**Context engineering:** `ai_service.py` always extracts up to 10 seconds before and after the selected region and passes them to the provider. This ensures the AI-generated segment fits musically into the surrounding track.

---

## Technology Stack

| Concern | Tool | Notes |
|---------|------|-------|
| Backend framework | FastAPI + uvicorn | async, background tasks for AI jobs |
| Frontend | Streamlit | browser-based Python UI, easy web deployment later |
| Audio I/O | librosa + FFmpeg | mp3/wav/m4a/flac all transparent |
| Pitch → MIDI | Basic Pitch (Spotify) | polyphonic, runs on CPU, `pip install basic-pitch` |
| MIDI → Audio | FluidSynth + midi2audio + GeneralUser.sf2 | free soundfont, default piano timbre |
| AI (local) | MusicGen `facebook/musicgen-small` via transformers | GPU recommended, free |
| AI (cloud) | Replicate API | ~$0.07/run, no local GPU needed |
| Testing | pytest + httpx | async-compatible, real small fixtures |
| Process control | `ctl` script (tmux-backed) | start/stop/restart/status/test |

---

## Testing Strategy

**Philosophy:** TDD per phase. Service methods written test-first. Real small fixtures (3-second WAV, minimal MIDI) committed to `tests/fixtures/`. No mocking audio processing — only mock external AI API calls.

| Layer | Command | What's covered |
|-------|---------|----------------|
| Unit | `ctl test unit` | Each service method in isolation |
| Route integration | `ctl test unit` | Full request/response via `httpx.AsyncClient` |
| Provider contract | `ctl test unit` | Both providers satisfy `AIProvider` ABC shape |
| End-to-end | `ctl test integration` | Upload → extract → synthesize → verify WAV non-empty |
| All | `ctl test` | Everything above |
| Watch mode | `ctl test watch` | TDD loop, re-runs on file change |

---

## Development Phases

### Phase 1 — Core Pipeline (MVP)
Upload mp3/wav → extract MIDI via Basic Pitch → synthesize WAV via FluidSynth → stream to browser for playback. Minimal Streamlit UI: file uploader, static waveform plot (matplotlib), play button, note list with number inputs.

**Done when:** `ctl test integration` passes full round-trip.

### Phase 2 — Microphone Input
Browser mic recording → audio blob → `POST /audio/record` → same pipeline as upload. Streamlit mic widget (`st.audio_input`).

**Done when:** Record tab works end-to-end; integration test extended to cover mic path.

### Phase 3 — Editing
Note list in editor: edit pitch (MIDI 0–127) and timing (start/end seconds) via number inputs. Region select: start/end time inputs, play selected region only. Re-synthesize on every edit.

**Done when:** Round-trip edit test passes (edit note → synthesize → verify pitch change in output audio).

### Phase 4 — AI Modification
Three mode buttons: Style Transfer, Melody Variation, Accompaniment. Local/Replicate toggle in sidebar. Async job polling with spinner. Before/after audio comparison toggle. Context engineering: 10s before + after segment sent to provider.

**Done when:** All three modes produce non-empty audio in both providers; integration test mocks provider and verifies context assembly.

### Phase 5 — Web UI (Future)
React + WaveSurfer.js frontend replacing Streamlit. Piano roll, click-and-drag region select, playback cursor. Zero backend changes — same FastAPI API.

---

## Dev Tooling

| Tool | Purpose |
|------|---------|
| `ctl [start\|stop\|restart\|status] [backend\|frontend]` | Process control via tmux named sessions |
| `ctl test [unit\|integration\|watch]` | Run test suite at any granularity |
| `/new-route` skill | Checklist: route → schema → service → test → register in `main.py` |
| Context7 MCP | On-demand library docs (Basic Pitch, FastAPI, Streamlit, MusicGen) |
| Git worktrees | One worktree per phase via `superpowers:using-git-worktrees` |
| Project `Stop` hook | End of each session: runs `ctl test`, checks if `ctl` needs updating |

---

## Audio Format Notes

- **Input:** mp3, wav, m4a, flac, ogg — transparent via librosa + FFmpeg (`apt install ffmpeg`)
- **Internal:** WAV (lossless, no decode overhead during processing)
- **MIDI:** `.mid` files per track + note events as JSON (UUID-keyed)
- **Output:** WAV for playback; MP3 export via pydub
- **No pro format required** — mp3 upload works out of the box once FFmpeg is installed
