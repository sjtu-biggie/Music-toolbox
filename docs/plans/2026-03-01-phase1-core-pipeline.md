# Phase 1: Core Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upload an mp3/wav → extract MIDI via Basic Pitch → synthesize WAV via FluidSynth → stream back to browser for playback, with a minimal Streamlit UI.

**Architecture:** FastAPI backend (port 8000) + Streamlit frontend (port 8501) as separate processes. All audio processing in backend services. Frontend is a thin HTTP client.

**Tech Stack:** FastAPI, uvicorn, Streamlit, librosa, basic-pitch, FluidSynth + midi2audio + pretty-midi, soundfile, httpx, pytest, numpy

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `backend/config.py`
- Create: `backend/__init__.py`
- Create: `backend/api/__init__.py`
- Create: `backend/api/routes/__init__.py`
- Create: `backend/services/__init__.py`
- Create: `backend/providers/__init__.py`
- Create: `backend/repositories/__init__.py`
- Create: `backend/models/__init__.py`
- Create: `frontend/__init__.py`
- Create: `frontend/pages/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/backend/__init__.py`
- Create: `tests/fixtures/.gitkeep`
- Create: `logs/.gitkeep`
- Create: `assets/soundfonts/.gitkeep`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "ai-music"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "python-multipart>=0.0.9",
    "pydantic>=2.7.0",
    "librosa>=0.10.0",
    "basic-pitch>=0.3.0",
    "midi2audio>=0.1.1",
    "pyfluidsynth>=1.3.0",
    "pretty-midi>=0.2.10",
    "soundfile>=0.12.0",
    "httpx>=0.27.0",
    "streamlit>=1.35.0",
    "matplotlib>=3.8.0",
    "numpy>=1.26.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-watch>=4.2.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["integration: marks tests as integration tests (deselect with '-m not integration')"]

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:BuildBackend"
```

**Step 2: Create backend/config.py**

```python
from pathlib import Path


class StaticConfig:
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 8501

    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    TRACKS_DIR: Path = DATA_DIR / "tracks"
    AUDIO_DIR: Path = DATA_DIR / "audio"
    MIDI_DIR: Path = DATA_DIR / "midi"
    JOBS_DIR: Path = DATA_DIR / "jobs"

    SOUNDFONT_PATH: Path = BASE_DIR / "assets" / "soundfonts" / "GeneralUser.sf2"
    INTERNAL_SAMPLE_RATE: int = 22050   # canonical rate for all stored/processed audio
    FLUIDSYNTH_SAMPLE_RATE: int = 22050 # passed to FluidSynth -r flag
    SPLICE_CROSSFADE_MS: int = 80       # crossfade at AI splice boundaries (Phase 4)
    WAVEFORM_MAX_POINTS: int = 1000
    AI_CONTEXT_SECONDS: float = 10.0

    REPLICATE_API_TOKEN: str = ""  # set via REPLICATE_API_TOKEN env var

    @classmethod
    def ensure_dirs(cls) -> None:
        for d in [cls.TRACKS_DIR, cls.AUDIO_DIR, cls.MIDI_DIR, cls.JOBS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
```

**Step 3: Create all `__init__.py` files (empty) and placeholder files**

```bash
touch backend/__init__.py backend/api/__init__.py backend/api/routes/__init__.py
touch backend/services/__init__.py backend/providers/__init__.py
touch backend/repositories/__init__.py backend/models/__init__.py
touch frontend/__init__.py frontend/pages/__init__.py
touch tests/__init__.py tests/backend/__init__.py
mkdir -p tests/fixtures logs assets/soundfonts data
touch tests/fixtures/.gitkeep logs/.gitkeep assets/soundfonts/.gitkeep
```

**Step 4: Install system dependencies**

```bash
sudo apt-get install -y ffmpeg fluidsynth
pip install -e .
```

Expected: no errors. Verify:
```bash
python -c "import librosa; import basic_pitch; print('OK')"
```

**Step 5: Commit**

```bash
git add pyproject.toml backend/ frontend/ tests/ logs/ assets/ data/
git commit -m "feat: project scaffold with config and directory structure"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `backend/models/schemas.py`
- Create: `tests/backend/test_schemas.py`

**Step 1: Write failing test**

```python
# tests/backend/test_schemas.py
from uuid import UUID
from datetime import datetime
from backend.models.schemas import Track, Note, AIJob


def test_track_has_uuid_and_timestamps():
    track = Track(filename="song.mp3", duration_sec=3.0, sample_rate=22050, status="ready")
    assert isinstance(track.id, UUID)
    assert isinstance(track.created_at, datetime)
    assert isinstance(track.updated_at, datetime)


def test_note_links_to_track():
    from uuid import uuid4
    track_id = uuid4()
    note = Note(track_id=track_id, pitch_midi=60, start_sec=0.0, end_sec=0.5, velocity=80)
    assert note.track_id == track_id
    assert isinstance(note.id, UUID)


def test_aijob_status_default_pending():
    from uuid import uuid4
    job = AIJob(
        track_id=uuid4(),
        mode="style",
        prompt="make it jazzy",
        provider="local",
        start_sec=1.0,
        end_sec=3.0,
    )
    assert job.status == "pending"
    assert job.result_path is None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/backend/test_schemas.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.models.schemas'`

**Step 3: Implement schemas**

```python
# backend/models/schemas.py
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Track(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    duration_sec: float
    sample_rate: int
    status: Literal["uploading", "ready", "processing"]
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Note(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    pitch_midi: int   # 0-127
    start_sec: float
    end_sec: float
    velocity: int     # 0-127


class AIJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    mode: Literal["style", "melody", "accompaniment"]
    prompt: str
    provider: Literal["local", "replicate"]
    start_sec: float
    end_sec: float
    status: Literal["pending", "running", "done", "failed"] = "pending"
    result_path: str | None = None
    error_msg: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_schemas.py -v
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add backend/models/schemas.py tests/backend/test_schemas.py
git commit -m "feat: add DB-ready Pydantic schemas (Track, Note, AIJob)"
```

---

## Task 3: Repository Layer

**Files:**
- Create: `backend/repositories/base.py`
- Create: `backend/repositories/file_repo.py`
- Create: `tests/backend/test_file_repo.py`

**Step 1: Write failing test**

```python
# tests/backend/test_file_repo.py
import pytest
from uuid import uuid4
from backend.models.schemas import Track
from backend.repositories.file_repo import FileTrackRepository
from backend.config import StaticConfig


@pytest.fixture(autouse=True)
def setup_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(StaticConfig, "TRACKS_DIR", tmp_path / "tracks")
    monkeypatch.setattr(StaticConfig, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(StaticConfig, "MIDI_DIR", tmp_path / "midi")
    monkeypatch.setattr(StaticConfig, "JOBS_DIR", tmp_path / "jobs")
    StaticConfig.ensure_dirs()


@pytest.mark.asyncio
async def test_save_and_get_track():
    repo = FileTrackRepository()
    track = Track(filename="song.mp3", duration_sec=3.0, sample_rate=22050, status="ready")
    await repo.save(track)
    loaded = await repo.get(track.id)
    assert loaded.id == track.id
    assert loaded.filename == "song.mp3"


@pytest.mark.asyncio
async def test_get_missing_track_raises():
    repo = FileTrackRepository()
    with pytest.raises(KeyError):
        await repo.get(uuid4())
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_file_repo.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# backend/repositories/base.py
from abc import ABC, abstractmethod
from uuid import UUID
from ..models.schemas import Track


class TrackRepository(ABC):
    @abstractmethod
    async def save(self, track: Track) -> Track: ...

    @abstractmethod
    async def get(self, track_id: UUID) -> Track: ...
```

```python
# backend/repositories/file_repo.py
import json
from uuid import UUID
from pathlib import Path
from .base import TrackRepository
from ..models.schemas import Track
from ..config import StaticConfig


class FileTrackRepository(TrackRepository):
    def _path(self, track_id: UUID) -> Path:
        return StaticConfig.TRACKS_DIR / f"{track_id}.json"

    async def save(self, track: Track) -> Track:
        StaticConfig.TRACKS_DIR.mkdir(parents=True, exist_ok=True)
        self._path(track.id).write_text(track.model_dump_json())
        return track

    async def get(self, track_id: UUID) -> Track:
        path = self._path(track_id)
        if not path.exists():
            raise KeyError(f"Track {track_id} not found")
        return Track.model_validate_json(path.read_text())
```

**Step 4: Run to verify passes**

```bash
pytest tests/backend/test_file_repo.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add backend/repositories/ tests/backend/test_file_repo.py
git commit -m "feat: file-based repository with abstract interface (Supabase-swap-ready)"
```

---

## Task 4: Test Fixtures

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/fixtures/sample.wav` (generated, committed)
- Create: `tests/fixtures/sample.mid` (generated, committed)

**Step 1: Create conftest.py with fixture generators**

```python
# tests/conftest.py
import numpy as np
import soundfile as sf
import pretty_midi
import pytest
from pathlib import Path
from backend.config import StaticConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_sample_wav() -> Path:
    path = FIXTURES_DIR / "sample.wav"
    if path.exists():
        return path
    sr = 22050
    t = np.linspace(0, 3.0, int(sr * 3.0))
    audio = 0.5 * np.sin(2 * np.pi * 440.0 * t)  # 440Hz sine, 3 seconds
    sf.write(str(path), audio, sr)
    return path


def _make_sample_mid() -> Path:
    path = FIXTURES_DIR / "sample.mid"
    if path.exists():
        return path
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5))
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=62, start=0.5, end=1.0))
    pm.instruments.append(inst)
    pm.write(str(path))
    return path


@pytest.fixture(scope="session", autouse=True)
def generate_fixtures():
    FIXTURES_DIR.mkdir(exist_ok=True)
    _make_sample_wav()
    _make_sample_mid()


@pytest.fixture
def sample_wav_path() -> Path:
    return FIXTURES_DIR / "sample.wav"


@pytest.fixture
def sample_mid_path() -> Path:
    return FIXTURES_DIR / "sample.mid"


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect all data dirs to tmp_path for test isolation."""
    monkeypatch.setattr(StaticConfig, "TRACKS_DIR", tmp_path / "tracks")
    monkeypatch.setattr(StaticConfig, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(StaticConfig, "MIDI_DIR", tmp_path / "midi")
    monkeypatch.setattr(StaticConfig, "JOBS_DIR", tmp_path / "jobs")
    StaticConfig.ensure_dirs()
    return tmp_path
```

**Step 2: Run to generate fixtures**

```bash
pytest tests/ -v --collect-only
```
Expected: fixtures generated, tests collected

**Step 3: Commit fixtures**

```bash
git add tests/conftest.py tests/fixtures/
git commit -m "feat: test fixtures (3s sine WAV, minimal MIDI)"
```

---

## Task 5: audio_service

**Files:**
- Create: `backend/services/audio_service.py`
- Create: `tests/backend/test_audio_service.py`

**Step 1: Write failing tests**

```python
# tests/backend/test_audio_service.py
import numpy as np
import pytest
from pathlib import Path
from backend.services.audio_service import load_audio, get_waveform_data, convert_to_wav


def test_load_audio_returns_numpy_and_sr(sample_wav_path):
    from backend.config import StaticConfig
    audio, sr = load_audio(sample_wav_path)
    assert isinstance(audio, np.ndarray)
    assert sr == StaticConfig.INTERNAL_SAMPLE_RATE  # always canonical rate
    assert sr == 22050
    assert len(audio) > 0


def test_load_audio_supports_mp3(tmp_path):
    # pydub can create mp3 from wav for testing; skip if ffmpeg not available
    pytest.importorskip("pydub")
    from pydub import AudioSegment
    wav = tmp_path / "test.wav"
    mp3 = tmp_path / "test.mp3"
    import soundfile as sf
    import numpy as np
    sf.write(str(wav), np.zeros(22050), 22050)
    AudioSegment.from_wav(str(wav)).export(str(mp3), format="mp3")
    audio, sr = load_audio(mp3)
    assert len(audio) > 0


def test_get_waveform_data_shape(sample_wav_path):
    audio, sr = load_audio(sample_wav_path)
    result = get_waveform_data(audio, sr, max_points=100)
    assert "times" in result and "amplitudes" in result and "duration_sec" in result
    assert len(result["times"]) <= 100
    assert len(result["times"]) == len(result["amplitudes"])
    assert abs(result["duration_sec"] - 3.0) < 0.1


def test_convert_to_wav(sample_wav_path, tmp_path):
    import soundfile as sf
    from backend.config import StaticConfig
    dest = tmp_path / "out.wav"
    convert_to_wav(sample_wav_path, dest)
    assert dest.exists()
    assert dest.stat().st_size > 0
    _, sr = sf.read(str(dest))
    assert sr == StaticConfig.INTERNAL_SAMPLE_RATE  # must be canonical rate after conversion
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_audio_service.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# backend/services/audio_service.py
from pathlib import Path
import numpy as np
import librosa
import soundfile as sf
from ..config import StaticConfig


def load_audio(file_path: Path) -> tuple[np.ndarray, int]:
    """
    Load any audio format (mp3/wav/m4a/flac) to mono float32 numpy array at INTERNAL_SAMPLE_RATE.
    Always returns (audio, INTERNAL_SAMPLE_RATE) regardless of source sample rate.
    """
    audio, sr = librosa.load(str(file_path), sr=StaticConfig.INTERNAL_SAMPLE_RATE, mono=True)
    return audio.astype(np.float32), StaticConfig.INTERNAL_SAMPLE_RATE


def save_audio(audio: np.ndarray, sr: int, dest_path: Path) -> None:
    sf.write(str(dest_path), audio, sr, subtype="PCM_16")


def get_waveform_data(
    audio: np.ndarray, sr: int, max_points: int = StaticConfig.WAVEFORM_MAX_POINTS
) -> dict:
    """Downsample audio to at most max_points for waveform visualization."""
    duration = len(audio) / sr
    step = max(1, len(audio) // max_points)
    times = (np.arange(0, len(audio), step) / sr).tolist()
    amplitudes = audio[::step].tolist()
    return {"times": times, "amplitudes": amplitudes, "duration_sec": duration}


def convert_to_wav(src_path: Path, dest_path: Path) -> None:
    """
    Convert any supported audio format to WAV at INTERNAL_SAMPLE_RATE (22050 Hz).
    All audio stored on disk is always at this canonical rate.
    """
    audio, sr = load_audio(src_path)   # load_audio already resamples to INTERNAL_SAMPLE_RATE
    save_audio(audio, sr, dest_path)
```

**Step 4: Run to verify passes**

```bash
pytest tests/backend/test_audio_service.py -v
```
Expected: 3-4 passed (mp3 test skipped if pydub absent)

**Step 5: Commit**

```bash
git add backend/services/audio_service.py tests/backend/test_audio_service.py
git commit -m "feat: audio_service — load, waveform extraction, format conversion"
```

---

## Task 6: midi_service

**Files:**
- Create: `backend/services/midi_service.py`
- Create: `tests/backend/test_midi_service.py`

> **Note:** Basic Pitch model downloads on first run (~50MB). Run `python -c "from basic_pitch.inference import predict"` once before tests to cache it.

**Step 1: Write failing tests**

```python
# tests/backend/test_midi_service.py
import pytest
from pathlib import Path
from uuid import uuid4
from backend.services.midi_service import extract_midi, synthesize_midi, notes_to_midi
from backend.models.schemas import Note
from backend.config import StaticConfig


def test_extract_midi_returns_notes(sample_wav_path, isolated_dirs):
    midi_path = isolated_dirs / "out.mid"
    notes = extract_midi(sample_wav_path, midi_path, track_id=uuid4())
    assert midi_path.exists()
    assert isinstance(notes, list)
    # Basic Pitch should detect at least one note from a 440Hz sine
    assert len(notes) >= 1
    assert all(isinstance(n, Note) for n in notes)
    assert all(0 <= n.pitch_midi <= 127 for n in notes)


def test_synthesize_midi_produces_wav_at_canonical_rate(sample_mid_path, isolated_dirs):
    import soundfile as sf
    out_wav = isolated_dirs / "synth.wav"
    synthesize_midi(sample_mid_path, out_wav)
    assert out_wav.exists()
    assert out_wav.stat().st_size > 0
    _, sr = sf.read(str(out_wav))
    assert sr == StaticConfig.INTERNAL_SAMPLE_RATE


def test_notes_to_midi_roundtrip(isolated_dirs):
    track_id = uuid4()
    notes = [
        Note(track_id=track_id, pitch_midi=60, start_sec=0.0, end_sec=0.5, velocity=80),
        Note(track_id=track_id, pitch_midi=64, start_sec=0.5, end_sec=1.0, velocity=80),
    ]
    midi_path = isolated_dirs / "roundtrip.mid"
    notes_to_midi(notes, midi_path)
    assert midi_path.exists()
    # Re-extract and verify pitches roughly match
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    pitches = [n.pitch for inst in pm.instruments for n in inst.notes]
    assert 60 in pitches
    assert 64 in pitches
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_midi_service.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# backend/services/midi_service.py
from pathlib import Path
from uuid import UUID, uuid4
import pretty_midi
from basic_pitch.inference import predict
from midi2audio import FluidSynth
from ..config import StaticConfig
from ..models.schemas import Note


def extract_midi(audio_path: Path, midi_path: Path, track_id: UUID) -> list[Note]:
    """Extract MIDI from audio using Basic Pitch. Returns list of Note objects."""
    _model_output, midi_data, _note_events = predict(str(audio_path))
    midi_data.write(str(midi_path))
    notes = []
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            notes.append(Note(
                id=uuid4(),
                track_id=track_id,
                pitch_midi=note.pitch,
                start_sec=float(note.start),
                end_sec=float(note.end),
                velocity=int(note.velocity),
            ))
    return notes


def synthesize_midi(midi_path: Path, audio_path: Path) -> None:
    """Render .mid to .wav using FluidSynth at FLUIDSYNTH_SAMPLE_RATE (22050 Hz)."""
    fs = FluidSynth(
        str(StaticConfig.SOUNDFONT_PATH),
        sample_rate=StaticConfig.FLUIDSYNTH_SAMPLE_RATE,
    )
    fs.midi_to_audio(str(midi_path), str(audio_path))


def notes_to_midi(notes: list[Note], midi_path: Path, tempo: float = 120.0) -> None:
    """Write Note objects back to a .mid file (used after editing)."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    instrument = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano
    for note in sorted(notes, key=lambda n: n.start_sec):
        instrument.notes.append(pretty_midi.Note(
            velocity=note.velocity,
            pitch=note.pitch_midi,
            start=note.start_sec,
            end=note.end_sec,
        ))
    pm.instruments.append(instrument)
    pm.write(str(midi_path))
```

**Step 4: Run to verify passes**

```bash
pytest tests/backend/test_midi_service.py -v
```
Expected: 3 passed. Note: `test_extract_midi_returns_notes` may take 10-30s first run (model load).

**Step 5: Download soundfont (one-time)**

```bash
wget -O assets/soundfonts/GeneralUser.sf2 \
  "https://dl.dropboxusercontent.com/s/4x37tu9yw3orjns/GeneralUser%20GS%20v1.471.sf2"
```
(Or any free General MIDI .sf2 — search "GeneralUser GS soundfont download")

**Step 6: Commit**

```bash
git add backend/services/midi_service.py tests/backend/test_midi_service.py
git add assets/soundfonts/GeneralUser.sf2
git commit -m "feat: midi_service — Basic Pitch extraction, FluidSynth synthesis, notes↔MIDI"
```

---

## Task 7: FastAPI App + Audio Routes

**Files:**
- Create: `backend/main.py`
- Create: `backend/api/routes/audio.py`
- Create: `tests/backend/test_routes.py`

**Step 1: Write failing tests**

```python
# tests/backend/test_routes.py
import pytest
import io
import soundfile as sf
import numpy as np
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.config import StaticConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(isolated_dirs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def wav_bytes():
    buf = io.BytesIO()
    sr = 22050
    audio = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, sr))
    sf.write(buf, audio, sr, format="WAV")
    buf.seek(0)
    return buf.read()


@pytest.mark.anyio
async def test_upload_returns_track_id(client, wav_bytes):
    resp = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "track_id" in data
    assert data["duration_sec"] > 0


@pytest.mark.anyio
async def test_waveform_returns_arrays(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    track_id = upload.json()["track_id"]
    resp = await client.get(f"/audio/{track_id}/waveform")
    assert resp.status_code == 200
    data = resp.json()
    assert "times" in data and "amplitudes" in data
    assert len(data["times"]) > 0


@pytest.mark.anyio
async def test_playback_streams_audio(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    track_id = upload.json()["track_id"]
    resp = await client.get(f"/audio/{track_id}/playback")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"


@pytest.mark.anyio
async def test_upload_rejects_bad_format(client):
    resp = await client.post(
        "/audio/upload",
        files={"file": ("test.xyz", b"garbage", "application/octet-stream")},
    )
    assert resp.status_code == 400
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_routes.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.main'`

**Step 3: Create main.py**

```python
# backend/main.py
from fastapi import FastAPI
from .api.routes import audio, midi

app = FastAPI(title="AI Music API", version="0.1.0")
app.include_router(audio.router)
app.include_router(midi.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Create audio routes**

```python
# backend/api/routes/audio.py
import shutil
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from ...config import StaticConfig
from ...models.schemas import Track
from ...repositories.file_repo import FileTrackRepository
from ...services.audio_service import convert_to_wav, get_waveform_data, load_audio

router = APIRouter(prefix="/audio", tags=["audio"])
_repo = FileTrackRepository()
_ALLOWED = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(400, f"Unsupported format '{suffix}'. Allowed: {_ALLOWED}")
    StaticConfig.ensure_dirs()
    from uuid import uuid4
    track_id = uuid4()
    raw_path = StaticConfig.TRACKS_DIR / f"{track_id}{suffix}"
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    convert_to_wav(raw_path, wav_path)
    audio, sr = load_audio(wav_path)
    track = Track(
        id=track_id,
        filename=file.filename,
        duration_sec=round(len(audio) / sr, 3),
        sample_rate=sr,
        status="ready",
    )
    await _repo.save(track)
    return {"track_id": str(track_id), "duration_sec": track.duration_sec, "sample_rate": sr}


@router.get("/{track_id}/waveform")
async def get_waveform(track_id: str):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    audio, sr = load_audio(wav_path)
    return get_waveform_data(audio, sr)


@router.get("/{track_id}/playback")
async def get_playback(track_id: str):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    return StreamingResponse(open(wav_path, "rb"), media_type="audio/wav")
```

**Step 5: Run to verify passes**

```bash
pytest tests/backend/test_routes.py -v -k "audio"
```
Expected: 4 passed

**Step 6: Commit**

```bash
git add backend/main.py backend/api/routes/audio.py tests/backend/test_routes.py
git commit -m "feat: FastAPI app + audio routes (upload, waveform, playback)"
```

---

## Task 8: MIDI Routes

**Files:**
- Modify: `backend/api/routes/midi.py` (create)
- Modify: `backend/main.py` (already includes midi router)
- Modify: `tests/backend/test_routes.py` (add MIDI tests)

**Step 1: Add MIDI tests to test_routes.py**

```python
# append to tests/backend/test_routes.py

@pytest.mark.anyio
async def test_extract_midi_returns_notes(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    track_id = upload.json()["track_id"]
    resp = await client.post(f"/midi/{track_id}/extract")
    assert resp.status_code == 200
    data = resp.json()
    assert "notes" in data
    assert isinstance(data["notes"], list)


@pytest.mark.anyio
async def test_synthesize_after_extract(client, wav_bytes):
    upload = await client.post(
        "/audio/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    track_id = upload.json()["track_id"]
    await client.post(f"/midi/{track_id}/extract")
    resp = await client.post(f"/midi/{track_id}/synthesize")
    assert resp.status_code == 200
```

**Step 2: Run to verify new tests fail**

```bash
pytest tests/backend/test_routes.py::test_extract_midi_returns_notes -v
```
Expected: 404 (route not registered yet)

**Step 3: Create midi routes**

```python
# backend/api/routes/midi.py
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ...config import StaticConfig
from ...models.schemas import Note
from ...repositories.file_repo import FileTrackRepository
from ...services.midi_service import extract_midi, notes_to_midi, synthesize_midi

router = APIRouter(prefix="/midi", tags=["midi"])
_repo = FileTrackRepository()


def _notes_path(track_id: str) -> Path:
    return StaticConfig.MIDI_DIR / f"{track_id}_notes.json"


def _midi_path(track_id: str) -> Path:
    return StaticConfig.MIDI_DIR / f"{track_id}.mid"


def _synth_path(track_id: str) -> Path:
    return StaticConfig.AUDIO_DIR / f"{track_id}_synth.wav"


@router.post("/{track_id}/extract")
async def extract(track_id: str):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    from uuid import UUID
    midi_path = _midi_path(track_id)
    StaticConfig.MIDI_DIR.mkdir(parents=True, exist_ok=True)
    notes = extract_midi(wav_path, midi_path, track_id=UUID(track_id))
    notes_data = [n.model_dump(mode="json") for n in notes]
    _notes_path(track_id).write_text(json.dumps(notes_data))
    return {"notes": notes_data}


@router.get("/{track_id}")
async def get_notes(track_id: str):
    path = _notes_path(track_id)
    if not path.exists():
        raise HTTPException(404, "MIDI not extracted yet")
    return {"notes": json.loads(path.read_text())}


@router.put("/{track_id}/notes/{note_id}")
async def update_note(track_id: str, note_id: str, payload: dict):
    path = _notes_path(track_id)
    if not path.exists():
        raise HTTPException(404, "MIDI not extracted yet")
    notes_data = json.loads(path.read_text())
    for note in notes_data:
        if note["id"] == note_id:
            note.update({k: v for k, v in payload.items() if k in ("pitch_midi", "start_sec", "end_sec", "velocity")})
            path.write_text(json.dumps(notes_data))
            return note
    raise HTTPException(404, f"Note {note_id} not found")


@router.post("/{track_id}/synthesize")
async def synthesize(track_id: str):
    path = _notes_path(track_id)
    if not path.exists():
        raise HTTPException(404, "MIDI not extracted yet")
    notes = [Note.model_validate(n) for n in json.loads(path.read_text())]
    midi_path = _midi_path(track_id)
    notes_to_midi(notes, midi_path)
    synth_path = _synth_path(track_id)
    synthesize_midi(midi_path, synth_path)
    return {"playback_url": f"/audio/{track_id}/synth"}


@router.get("/{track_id}/playback")
async def midi_playback(track_id: str):
    synth_path = _synth_path(track_id)
    if not synth_path.exists():
        raise HTTPException(404, "Not synthesized yet — call POST /midi/{id}/synthesize first")
    return StreamingResponse(open(synth_path, "rb"), media_type="audio/wav")
```

**Step 4: Register midi router in main.py** (already done in Task 7 — verify it's there)

**Step 5: Run to verify passes**

```bash
pytest tests/backend/test_routes.py -v
```
Expected: all pass

**Step 6: Commit**

```bash
git add backend/api/routes/midi.py tests/backend/test_routes.py
git commit -m "feat: MIDI routes (extract, get notes, update note, synthesize)"
```

---

## Task 9: Streamlit Frontend

**Files:**
- Create: `frontend/api_client.py`
- Create: `frontend/app.py`
- Create: `frontend/pages/upload.py`
- Create: `frontend/pages/editor.py`

**Step 1: Create api_client.py**

```python
# frontend/api_client.py
import httpx
from pathlib import Path

BACKEND_URL = "http://localhost:8000"
_client = httpx.Client(base_url=BACKEND_URL, timeout=120.0)


def upload_audio(file_bytes: bytes, filename: str) -> dict:
    resp = _client.post("/audio/upload", files={"file": (filename, file_bytes, "audio/wav")})
    resp.raise_for_status()
    return resp.json()


def get_waveform(track_id: str) -> dict:
    resp = _client.get(f"/audio/{track_id}/waveform")
    resp.raise_for_status()
    return resp.json()


def get_playback_url(track_id: str) -> str:
    return f"{BACKEND_URL}/audio/{track_id}/playback"


def extract_midi(track_id: str) -> dict:
    resp = _client.post(f"/midi/{track_id}/extract", timeout=120.0)
    resp.raise_for_status()
    return resp.json()


def get_notes(track_id: str) -> dict:
    resp = _client.get(f"/midi/{track_id}")
    resp.raise_for_status()
    return resp.json()


def update_note(track_id: str, note_id: str, payload: dict) -> dict:
    resp = _client.put(f"/midi/{track_id}/notes/{note_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


def synthesize(track_id: str) -> dict:
    resp = _client.post(f"/midi/{track_id}/synthesize", timeout=120.0)
    resp.raise_for_status()
    return resp.json()


def get_synth_playback_url(track_id: str) -> str:
    return f"{BACKEND_URL}/midi/{track_id}/playback"
```

**Step 2: Create app.py**

```python
# frontend/app.py
import streamlit as st

st.set_page_config(page_title="AI Music", layout="wide")
st.title("AI Music")

tab_upload, tab_editor = st.tabs(["Upload / Record", "Editor"])

with tab_upload:
    from pages.upload import render
    render()

with tab_editor:
    from pages.editor import render
    render()
```

**Step 3: Create upload page**

```python
# frontend/pages/upload.py
import streamlit as st
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import api_client


def render():
    st.header("Upload Audio")
    uploaded = st.file_uploader(
        "Upload mp3, wav, m4a, or flac", type=["mp3", "wav", "m4a", "flac", "ogg"]
    )
    if uploaded and st.button("Process"):
        with st.spinner("Uploading and processing..."):
            try:
                result = api_client.upload_audio(uploaded.read(), uploaded.name)
                st.session_state["track_id"] = result["track_id"]
                st.success(f"Track loaded — {result['duration_sec']:.1f}s at {result['sample_rate']}Hz")
                st.info("Switch to the Editor tab to view and play your track.")
            except Exception as e:
                st.error(f"Upload failed: {e}")
```

**Step 4: Create editor page**

```python
# frontend/pages/editor.py
import streamlit as st
import matplotlib.pyplot as plt
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import api_client


def render():
    st.header("Editor")
    track_id = st.session_state.get("track_id")
    if not track_id:
        st.info("Upload a track first.")
        return

    st.caption(f"Track ID: `{track_id}`")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Extract MIDI"):
            with st.spinner("Extracting pitch and rhythm (may take 30s)..."):
                try:
                    result = api_client.extract_midi(track_id)
                    st.session_state["notes"] = result["notes"]
                    st.success(f"Extracted {len(result['notes'])} notes")
                except Exception as e:
                    st.error(f"Extraction failed: {e}")

    with col2:
        if st.button("Synthesize & Play"):
            with st.spinner("Synthesizing..."):
                try:
                    api_client.synthesize(track_id)
                    st.success("Done!")
                except Exception as e:
                    st.error(f"Synthesis failed: {e}")

    # Waveform plot
    try:
        wf = api_client.get_waveform(track_id)
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.plot(wf["times"], wf["amplitudes"], linewidth=0.5, color="steelblue")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Amplitude")
        ax.set_title("Waveform")
        st.pyplot(fig)
        plt.close(fig)
    except Exception:
        pass

    # Playback
    st.subheader("Playback")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.caption("Original")
        st.audio(api_client.get_playback_url(track_id))
    with pcol2:
        st.caption("Synthesized (after Extract + Synthesize)")
        st.audio(api_client.get_synth_playback_url(track_id))

    # Note editor
    notes = st.session_state.get("notes", [])
    if notes:
        st.subheader(f"Notes ({len(notes)})")
        for note in notes[:50]:  # cap display at 50
            with st.expander(f"Note {note['pitch_midi']} | {note['start_sec']:.2f}s – {note['end_sec']:.2f}s"):
                new_pitch = st.number_input("Pitch (MIDI 0-127)", 0, 127, note["pitch_midi"], key=f"p_{note['id']}")
                new_start = st.number_input("Start (s)", 0.0, value=note["start_sec"], step=0.01, key=f"s_{note['id']}")
                new_end = st.number_input("End (s)", 0.0, value=note["end_sec"], step=0.01, key=f"e_{note['id']}")
                if st.button("Update", key=f"u_{note['id']}"):
                    api_client.update_note(track_id, note["id"], {
                        "pitch_midi": new_pitch, "start_sec": new_start, "end_sec": new_end
                    })
                    st.success("Updated — click Synthesize to hear changes")
```

**Step 5: Manual smoke test**

```bash
# Terminal 1 (backend)
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2 (frontend)
cd frontend && streamlit run app.py --server.port 8501
```
Open `http://localhost:8501` in Windows browser. Upload a short mp3. Verify: track loads, waveform displays, Extract MIDI runs, Synthesize produces playback audio.

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: Streamlit frontend (upload, waveform, note editor, playback)"
```

---

## Task 10: ctl Script

**Files:**
- Create: `scripts/ctl`

**Step 1: Create ctl**

```bash
#!/usr/bin/env bash
# scripts/ctl — process control for ai-music services
set -euo pipefail

BACKEND_SESSION="ai-music-backend"
FRONTEND_SESSION="ai-music-frontend"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_start_backend() {
    if tmux has-session -t "$BACKEND_SESSION" 2>/dev/null; then
        echo "Backend already running"; return
    fi
    mkdir -p "$PROJECT_ROOT/logs"
    tmux new-session -ds "$BACKEND_SESSION" \
        "cd '$PROJECT_ROOT/backend' && uvicorn main:app --reload --host 0.0.0.0 --port 8000 2>&1 | tee '$PROJECT_ROOT/logs/backend.log'"
    echo "Backend started → http://localhost:8000"
}

_start_frontend() {
    if tmux has-session -t "$FRONTEND_SESSION" 2>/dev/null; then
        echo "Frontend already running"; return
    fi
    mkdir -p "$PROJECT_ROOT/logs"
    tmux new-session -ds "$FRONTEND_SESSION" \
        "cd '$PROJECT_ROOT/frontend' && streamlit run app.py --server.port 8501 2>&1 | tee '$PROJECT_ROOT/logs/frontend.log'"
    echo "Frontend started → http://localhost:8501"
}

_stop() {
    local session="$1"
    if tmux has-session -t "$session" 2>/dev/null; then
        tmux kill-session -t "$session" && echo "Stopped $session"
    else
        echo "$session not running"
    fi
}

_status() {
    echo "Backend:  $(tmux has-session -t "$BACKEND_SESSION" 2>/dev/null && echo 'running' || echo 'stopped')"
    echo "Frontend: $(tmux has-session -t "$FRONTEND_SESSION" 2>/dev/null && echo 'running' || echo 'stopped')"
}

_test() {
    local mode="${1:-all}"
    cd "$PROJECT_ROOT"
    case "$mode" in
        unit)        pytest tests/ -v -m "not integration" ;;
        integration) bash scripts/run_integration_test.sh ;;
        watch)       pytest-watch tests/ -- -v -m "not integration" ;;
        *)           pytest tests/ -v -m "not integration" && bash scripts/run_integration_test.sh ;;
    esac
}

CMD="${1:-help}"
TARGET="${2:-all}"
case "$CMD" in
    start)
        [[ "$TARGET" == "backend"  || "$TARGET" == "all" ]] && _start_backend
        [[ "$TARGET" == "frontend" || "$TARGET" == "all" ]] && _start_frontend
        ;;
    stop)
        [[ "$TARGET" == "backend"  || "$TARGET" == "all" ]] && _stop "$BACKEND_SESSION"
        [[ "$TARGET" == "frontend" || "$TARGET" == "all" ]] && _stop "$FRONTEND_SESSION"
        ;;
    restart)
        "$0" stop "$TARGET"; sleep 1; "$0" start "$TARGET" ;;
    status) _status ;;
    test)   _test "${2:-all}" ;;
    logs)
        [[ "$TARGET" == "backend"  ]] && tail -f "$PROJECT_ROOT/logs/backend.log"
        [[ "$TARGET" == "frontend" ]] && tail -f "$PROJECT_ROOT/logs/frontend.log"
        ;;
    *)
        echo "Usage: ctl [start|stop|restart|status|test|logs] [backend|frontend|all]"
        echo "       ctl test [unit|integration|watch|all]"
        ;;
esac
```

**Step 2: Make executable**

```bash
chmod +x scripts/ctl
```

**Step 3: Smoke test**

```bash
scripts/ctl start
scripts/ctl status
# Expected: both running
scripts/ctl stop
scripts/ctl status
# Expected: both stopped
```

**Step 4: Commit**

```bash
git add scripts/ctl
git commit -m "feat: ctl control script (start/stop/restart/status/test/logs)"
```

---

## Task 11: Integration Test

**Files:**
- Create: `scripts/run_integration_test.sh`

**Step 1: Create integration test script**

```bash
#!/usr/bin/env bash
# scripts/run_integration_test.sh — Phase 1 end-to-end test
set -euo pipefail

BACKEND="http://localhost:8000"
FIXTURE="tests/fixtures/sample.wav"

echo "=== Integration Test: Phase 1 Core Pipeline ==="

# 1. Health check
echo "[1/4] Health check..."
curl -sf "$BACKEND/health" | grep '"ok"' > /dev/null
echo "      PASS"

# 2. Upload
echo "[2/4] Upload audio..."
RESPONSE=$(curl -sf -X POST "$BACKEND/audio/upload" \
  -F "file=@$FIXTURE;type=audio/wav")
TRACK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['track_id'])")
echo "      PASS — track_id=$TRACK_ID"

# 3. Extract MIDI
echo "[3/4] Extract MIDI..."
NOTES=$(curl -sf -X POST "$BACKEND/midi/$TRACK_ID/extract" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['notes']))")
echo "      PASS — $NOTES notes extracted"

# 4. Synthesize
echo "[4/4] Synthesize..."
curl -sf -X POST "$BACKEND/midi/$TRACK_ID/synthesize" > /dev/null
# Verify file exists
WAV="data/audio/${TRACK_ID}_synth.wav"
[[ -f "$WAV" ]] || { echo "FAIL — $WAV not found"; exit 1; }
SIZE=$(stat -c%s "$WAV")
[[ "$SIZE" -gt 1000 ]] || { echo "FAIL — $WAV is suspiciously small ($SIZE bytes)"; exit 1; }
echo "      PASS — synth.wav is ${SIZE} bytes"

echo ""
echo "=== All integration tests PASSED ==="
```

**Step 2: Make executable and test**

```bash
chmod +x scripts/run_integration_test.sh
scripts/ctl start backend
sleep 3  # wait for uvicorn to boot
scripts/run_integration_test.sh
```
Expected:
```
=== Integration Test: Phase 1 Core Pipeline ===
[1/4] Health check...       PASS
[2/4] Upload audio...       PASS — track_id=<uuid>
[3/4] Extract MIDI...       PASS — N notes extracted
[4/4] Synthesize...         PASS — synth.wav is XXXXX bytes
=== All integration tests PASSED ===
```

**Step 3: Commit**

```bash
git add scripts/run_integration_test.sh
git commit -m "feat: integration test script — full Phase 1 pipeline round-trip"
```

---

## Task 12: README

Update `README.md` with setup, run, and test instructions.

```markdown
# AI Music

AI-assisted music tool: sing or upload audio → MIDI extraction → synthesis → AI modification.

## Setup

**System dependencies:**
```bash
sudo apt-get install -y ffmpeg fluidsynth tmux
```

**Python dependencies:**
```bash
pip install -e .
```

**Soundfont** (required for synthesis): download any General MIDI `.sf2` to `assets/soundfonts/GeneralUser.sf2`

## Running

```bash
scripts/ctl start        # starts backend (port 8000) and frontend (port 8501)
scripts/ctl status       # check running state
scripts/ctl logs backend # tail backend logs
```

Open `http://localhost:8501` in your browser.

## Testing

```bash
scripts/ctl test unit         # unit tests only
scripts/ctl test integration  # end-to-end pipeline (requires backend running)
scripts/ctl test              # all tests
scripts/ctl test watch        # TDD watch mode
```

## Architecture

- `backend/` — FastAPI API (port 8000). Audio processing, MIDI, AI providers.
- `frontend/` — Streamlit UI (port 8501). Thin HTTP client only.
- `docs/plans/` — Phase implementation plans.
- `scripts/ctl` — process control.

See `docs/plans/2026-03-01-ai-music-design.md` for full design.
```

```bash
git add README.md
git commit -m "docs: README with setup, run, and test instructions"
```

---

## Phase 1 Complete Checklist

- [ ] `ctl test unit` — all pass
- [ ] `ctl test integration` — all pass
- [ ] Upload mp3 in browser → waveform visible
- [ ] Extract MIDI → note list visible
- [ ] Update a note pitch → synthesize → playback sounds different
- [ ] `ctl start` / `ctl stop` / `ctl status` work correctly
- [ ] README accurate and complete
