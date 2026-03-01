# Phase 4: AI Modification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three AI modification modes (Style Transfer, Melody Variation, Accompaniment) with a local MusicGen-Melody / Replicate toggle, async job execution, seamless audio splicing, and before/after comparison playback.

**Architecture:** `AIProvider` ABC with two implementations. `ai_service` handles segment slicing, provider dispatch, and seamless splicing (resample → duration-match → RMS-normalize → crossfade). FastAPI `BackgroundTasks` for async execution. Stale job recovery on server startup. Streamlit polls job status and presents a toggle comparison.

**Tech Stack:** `transformers` (MusicGenMelody), `replicate` SDK, `torchaudio`, `soundfile`, `librosa`, FastAPI `BackgroundTasks`.

**Prerequisite:** Phase 3 complete and passing.

**Key design decisions:**
- Model used: `facebook/musicgen-melody` — generates audio conditioned on both a text prompt **and** an audio melody reference (the selected segment). Output follows the original melody in a new style.
- Seamless fit: output is resampled to `INTERNAL_SAMPLE_RATE` (22050 Hz), duration-matched, RMS-normalized to original segment loudness, then crossfaded at splice boundaries.
- Stale job recovery: on startup, any job with `status = "running"` is reset to `"failed"` with `error_msg = "Server restarted"` so state is never corrupted.

---

## Task 1: Install AI Dependencies

**Step 1: Add to pyproject.toml dependencies**

```toml
# add to [project] dependencies in pyproject.toml:
"transformers>=4.40.0",
"torch>=2.2.0",
"torchaudio>=2.2.0",
"replicate>=0.29.0",
"scipy>=1.12.0",
```

**Step 2: Install**

```bash
pip install -e .
```

**Step 3: Pre-download MusicGen-Melody model (one-time, ~1.5 GB)**

```bash
python -c "
from transformers import AutoProcessor, MusicgenMelodyForConditionalGeneration
AutoProcessor.from_pretrained('facebook/musicgen-melody')
MusicgenMelodyForConditionalGeneration.from_pretrained('facebook/musicgen-melody')
print('MusicGen-Melody model cached.')
"
```

**Step 4: Set Replicate token (optional — only needed for Replicate provider)**

```bash
export REPLICATE_API_TOKEN="your_token_here"
# Add to ~/.zshrc or ~/.bashrc for persistence
```

**Step 5: Commit pyproject.toml change**

```bash
git add pyproject.toml
git commit -m "feat: add AI dependencies (transformers, torch, replicate)"
```

---

## Task 2: AIProvider ABC + Schemas

**Files:**
- Create: `backend/providers/base.py`
- Create: `backend/providers/__init__.py`
- Modify: `backend/models/schemas.py` (add `ErrorResponse`, update `AIJob`, fix `datetime.utcnow`)

**Step 1: Write failing tests**

```python
# tests/backend/test_ai_provider_contract.py
import pytest
from abc import ABC
from backend.providers.base import AIProvider


def test_aiprovider_is_abstract():
    assert issubclass(AIProvider, ABC)


def test_aiprovider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AIProvider()


def test_aiprovider_has_modify_method():
    assert hasattr(AIProvider, "modify")
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_ai_provider_contract.py -v
```

**Step 3: Implement AIProvider ABC**

```python
# backend/providers/base.py
from abc import ABC, abstractmethod
from typing import Literal


class AIProvider(ABC):
    @abstractmethod
    async def modify(
        self,
        segment_audio: bytes,        # WAV bytes at INTERNAL_SAMPLE_RATE (22050 Hz)
        segment_duration_sec: float, # exact duration; output must match this length
        mode: Literal["style", "melody", "accompaniment"],
        prompt: str,
    ) -> bytes:
        """
        Return modified segment audio as WAV bytes at INTERNAL_SAMPLE_RATE (22050 Hz).

        Implementations must:
        1. Use segment_audio as melody conditioning input so output follows original melody.
        2. Generate audio of approximately segment_duration_sec length.
        3. Resample output to INTERNAL_SAMPLE_RATE (22050 Hz) before returning.
        The caller (ai_service) handles duration trimming, RMS normalization, and crossfading.
        """
        ...
```

**Step 4: Update schemas.py**

Replace the `datetime.utcnow` calls and add `ErrorResponse` and `spliced_track_id`:

```python
# backend/models/schemas.py
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Track(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    duration_sec: float
    sample_rate: int = 22050
    status: Literal["uploading", "ready", "processing"]
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Note(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    pitch_midi: int   # 0–127
    start_sec: float
    end_sec: float
    velocity: int     # 0–127


class AIJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    mode: Literal["style", "melody", "accompaniment"]
    prompt: str
    provider: Literal["local", "replicate"]
    start_sec: float
    end_sec: float
    status: Literal["pending", "running", "done", "failed"] = "pending"
    result_path: str | None = None        # path to AI output WAV (pre-splice)
    spliced_track_id: str | None = None   # track_id of fully-spliced result
    error_msg: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ErrorResponse(BaseModel):
    error: str    # short machine-readable code e.g. "TrackNotFound"
    detail: str   # human-readable message
```

**Step 5: Run to verify passes**

```bash
pytest tests/backend/test_ai_provider_contract.py -v
```

**Step 6: Commit**

```bash
git add backend/providers/base.py backend/providers/__init__.py backend/models/schemas.py \
        tests/backend/test_ai_provider_contract.py
git commit -m "feat: AIProvider ABC + updated schemas (ErrorResponse, AIJob.spliced_track_id)"
```

---

## Task 3: StaticConfig — Add AI Constants

**Files:**
- Modify: `backend/config.py`

Add the three new constants to Phase 1's existing `StaticConfig`. `AI_CONTEXT_SECONDS` and `JOBS_DIR` already exist from Phase 1 — do not add duplicates.

```python
# backend/config.py — add to StaticConfig (Phase 1 already has AI_CONTEXT_SECONDS and JOBS_DIR):
INTERNAL_SAMPLE_RATE: int = 22050    # already added in Phase 1 as INTERNAL_SAMPLE_RATE
FLUIDSYNTH_SAMPLE_RATE: int = 22050  # already added in Phase 1
SPLICE_CROSSFADE_MS: int = 80        # NEW — crossfade duration at each splice boundary
```

> **Note:** `AI_CONTEXT_SECONDS: float = 10.0` was defined in Phase 1. It is used as a rough description
> in prompt context text ("segment has 10 seconds of music before and after"). You can reference it in
> `build_prompt()` if you want explicit context hints in the prompt, but it is not required.

No tests needed — config is tested implicitly by every other test that imports it.

```bash
git add backend/config.py
git commit -m "feat: add INTERNAL_SAMPLE_RATE, SPLICE_CROSSFADE_MS, JOBS_DIR to StaticConfig"
```

---

## Task 4: ai_service (Segment Slicing + Seamless Splice)

**Files:**
- Create: `backend/services/ai_service.py`
- Create: `tests/backend/test_ai_service.py`

**Design: decoupled post-processing pipeline.**
Each splice step is a standalone pure function `(np.ndarray, ...) -> np.ndarray`. `splice_segment()` composes them via keyword flags. Any step can be disabled or replaced without touching the others.

```
slice_segment()        → bytes sent to provider
build_prompt()         → text prompt sent to provider
dispatch()             → calls provider, returns raw WAV bytes

Post-processing (all inside splice_segment, each independently togglable):
  resample_audio()     → provider output → 22050 Hz
  rms_normalize()      → AI loudness → original segment loudness
  crossfade_edges()    → smooth the start and end boundaries
  match_duration()     → optional: force exact original length (default OFF)
```

**Crossfade design:** uses `before[-cf:]` (end of preceding audio) and `after[:cf]` (start of following audio) as blend references — NOT the original segment. This means crossfade works identically whether the AI output is longer, shorter, or the same duration as the segment.

### Step 1: Write failing tests

```python
# tests/backend/test_ai_service.py
import io
import numpy as np
import soundfile as sf
import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from backend.services.ai_service import (
    slice_segment, build_prompt, splice_segment,
    resample_audio, rms_normalize, crossfade_edges, match_duration,
    dispatch,
)
from backend.config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE


def _make_wav(duration_sec: float, freq: float = 440.0, amplitude: float = 0.3, sr: int = SR) -> bytes:
    """Generate a sine-wave WAV at the given sample rate."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def _make_array(duration_sec: float, freq: float = 440.0, amplitude: float = 0.3) -> np.ndarray:
    t = np.linspace(0, duration_sec, int(SR * duration_sec), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _read_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    return sf.read(io.BytesIO(wav_bytes))


# ── resample_audio ──────────────────────────────────────────────────────────

def test_resample_audio_no_op_when_same_rate():
    audio = _make_array(1.0)
    result = resample_audio(audio, src_sr=SR, target_sr=SR)
    np.testing.assert_array_equal(result, audio)


def test_resample_audio_changes_length():
    audio = _make_array(1.0)
    result = resample_audio(audio, src_sr=SR, target_sr=SR * 2)
    assert len(result) == pytest.approx(len(audio) * 2, abs=10)


def test_resample_audio_output_is_float32():
    audio = _make_array(1.0).astype(np.float64)
    result = resample_audio(audio, src_sr=44100, target_sr=SR)
    assert result.dtype == np.float32


# ── rms_normalize ────────────────────────────────────────────────────────────

def test_rms_normalize_matches_reference_loudness():
    quiet = _make_array(1.0, amplitude=0.05)
    loud_ref = _make_array(1.0, amplitude=0.5)
    normalized = rms_normalize(quiet, reference=loud_ref)
    norm_rms = np.sqrt(np.mean(normalized ** 2))
    ref_rms = np.sqrt(np.mean(loud_ref ** 2))
    assert abs(norm_rms - ref_rms) < 0.01


def test_rms_normalize_clips_to_safe_range():
    # A very quiet reference should still not produce values outside [-1, 1]
    audio = _make_array(1.0, amplitude=0.9)
    silent_ref = np.zeros(SR, dtype=np.float32)  # near-zero RMS
    result = rms_normalize(audio, reference=silent_ref)
    assert np.all(np.abs(result) <= 1.0)


# ── crossfade_edges ──────────────────────────────────────────────────────────

def test_crossfade_edges_first_sample_matches_before():
    """At sample 0 of modified, output should still be dominated by before."""
    before = _make_array(5.0, freq=440.0)
    modified = _make_array(3.0, freq=880.0)
    after = _make_array(5.0, freq=220.0)
    cf = int(SR * 0.08)
    result = crossfade_edges(modified, before=before, after=after, crossfade_samples=cf)
    # First sample: fade_in=0 → result[0] should be ~before[-cf] * 1.0, not modified[0]
    assert abs(result[0] - before[-cf]) < 0.01


def test_crossfade_edges_last_sample_matches_after():
    """At last sample of modified, output should be dominated by after."""
    before = _make_array(5.0, freq=440.0)
    modified = _make_array(3.0, freq=880.0)
    after = _make_array(5.0, freq=220.0)
    cf = int(SR * 0.08)
    result = crossfade_edges(modified, before=before, after=after, crossfade_samples=cf)
    # Last sample: fade_out=0 → result[-1] should be ~after[cf-1] * 1.0
    assert abs(result[-1] - after[cf - 1]) < 0.01


def test_crossfade_edges_zero_crossfade_returns_unchanged():
    before = _make_array(5.0)
    modified = _make_array(3.0, freq=880.0)
    after = _make_array(5.0)
    result = crossfade_edges(modified, before=before, after=after, crossfade_samples=0)
    np.testing.assert_array_equal(result, modified)


def test_crossfade_edges_does_not_change_length():
    before = _make_array(5.0)
    modified = _make_array(3.0, freq=880.0)
    after = _make_array(5.0)
    result = crossfade_edges(modified, before=before, after=after, crossfade_samples=int(SR * 0.08))
    assert len(result) == len(modified)


# ── match_duration ───────────────────────────────────────────────────────────

def test_match_duration_trims_longer_audio():
    audio = _make_array(6.0)
    result = match_duration(audio, target_samples=int(SR * 5.0))
    assert len(result) == int(SR * 5.0)


def test_match_duration_pads_shorter_audio_with_silence():
    audio = _make_array(3.0)
    target = int(SR * 5.0)
    result = match_duration(audio, target_samples=target)
    assert len(result) == target
    # Padded region must be silence
    assert np.all(result[len(audio):] == 0.0)


# ── slice_segment ────────────────────────────────────────────────────────────

def test_slice_segment_returns_correct_duration(tmp_path):
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(30.0))
    segment_bytes, duration = slice_segment(wav_path, start_sec=10.0, end_sec=15.0)
    audio, sr = _read_wav(segment_bytes)
    assert abs(len(audio) / sr - 5.0) < 0.05
    assert abs(duration - 5.0) < 0.05


def test_slice_segment_validates_start_ge_end(tmp_path):
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(10.0))
    with pytest.raises(ValueError, match="start_sec must be less than end_sec"):
        slice_segment(wav_path, start_sec=5.0, end_sec=3.0)


def test_slice_segment_validates_end_beyond_track(tmp_path):
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(10.0))
    with pytest.raises(ValueError, match="out of range"):
        slice_segment(wav_path, start_sec=8.0, end_sec=12.0)


def test_slice_segment_output_is_internal_sample_rate(tmp_path):
    """Output WAV must always be at INTERNAL_SAMPLE_RATE regardless of source rate."""
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(10.0, sr=44100))
    segment_bytes, _ = slice_segment(wav_path, start_sec=2.0, end_sec=5.0)
    _, sr = _read_wav(segment_bytes)
    assert sr == SR


# ── build_prompt ─────────────────────────────────────────────────────────────

def test_build_prompt_style_contains_mode_and_user_text():
    prompt = build_prompt("style", "make it jazzy")
    assert "jazzy" in prompt
    assert "style" in prompt.lower() or "genre" in prompt.lower()


def test_build_prompt_accompaniment_contains_mode_and_user_text():
    prompt = build_prompt("accompaniment", "add bass line")
    assert "accompaniment" in prompt.lower() or "harmonic" in prompt.lower()
    assert "bass line" in prompt


# ── splice_segment ───────────────────────────────────────────────────────────

def test_splice_segment_default_keeps_ai_duration(tmp_path):
    """Default (match_duration=False): total track length changes to reflect AI output length."""
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0))
    # AI returned 7s for a 5s segment → track should become 22s, not 20s
    modified_bytes = _make_wav(7.0, freq=880.0)
    spliced = splice_segment(wav_path, start_sec=5.0, end_sec=10.0, modified_wav=modified_bytes)
    spliced_audio, _ = _read_wav(spliced)
    # 20s - 5s + 7s = 22s; allow small crossfade tolerance
    assert abs(len(spliced_audio) / SR - 22.0) < 0.5


def test_splice_segment_force_duration_match_preserves_length(tmp_path):
    """With force_duration_match=True, total track length stays the same as original."""
    wav_path = tmp_path / "track.wav"
    original_bytes = _make_wav(20.0)
    wav_path.write_bytes(original_bytes)
    modified_bytes = _make_wav(7.0, freq=880.0)   # longer than 5s segment
    spliced = splice_segment(
        wav_path, start_sec=5.0, end_sec=10.0,
        modified_wav=modified_bytes,
        force_duration_match=True,
    )
    original_audio, _ = _read_wav(original_bytes)
    spliced_audio, _ = _read_wav(spliced)
    assert abs(len(spliced_audio) - len(original_audio)) < SR * 0.1


def test_splice_segment_modified_audio_has_energy(tmp_path):
    """The spliced region must contain energy (not silence)."""
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0, freq=440.0))
    modified_bytes = _make_wav(5.0, freq=880.0)
    spliced = splice_segment(wav_path, start_sec=5.0, end_sec=10.0, modified_wav=modified_bytes)
    spliced_audio, sr = _read_wav(spliced)
    region = spliced_audio[int(5.5 * sr) : int(9.5 * sr)]  # avoid crossfade zones
    assert np.sqrt(np.mean(region ** 2)) > 0.001


def test_splice_segment_no_normalize_loudness(tmp_path):
    """normalize_loudness=False: AI output loudness is preserved as-is."""
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0, amplitude=0.1))    # quiet original
    modified_bytes = _make_wav(5.0, freq=880.0, amplitude=0.8)  # loud AI output
    spliced = splice_segment(
        wav_path, start_sec=5.0, end_sec=10.0,
        modified_wav=modified_bytes,
        normalize_loudness=False,
    )
    spliced_audio, sr = _read_wav(spliced)
    region = spliced_audio[int(5.5 * sr) : int(9.5 * sr)]
    # RMS should remain close to 0.8, not scaled down to 0.1
    assert np.sqrt(np.mean(region ** 2)) > 0.3


def test_splice_segment_no_crossfade_still_works(tmp_path):
    """crossfade_ms=0 disables crossfade; splice should still complete correctly."""
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0))
    modified_bytes = _make_wav(5.0, freq=880.0)
    spliced = splice_segment(
        wav_path, start_sec=5.0, end_sec=10.0,
        modified_wav=modified_bytes,
        crossfade_ms=0,
    )
    assert len(spliced) > 0


# ── dispatch ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_calls_provider_with_correct_args(tmp_path):
    mock_provider = AsyncMock()
    mock_provider.modify = AsyncMock(return_value=_make_wav(5.0, freq=880.0))

    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0))

    result = await dispatch(
        provider=mock_provider,
        wav_path=wav_path,
        start_sec=5.0,
        end_sec=10.0,
        mode="style",
        prompt="make it jazzy",
    )
    assert isinstance(result, bytes)
    mock_provider.modify.assert_called_once()
    kwargs = mock_provider.modify.call_args.kwargs
    assert "segment_audio" in kwargs
    assert "segment_duration_sec" in kwargs
    assert abs(kwargs["segment_duration_sec"] - 5.0) < 0.1
    assert kwargs["mode"] == "style"
    assert "jazzy" in kwargs["prompt"]
```

### Step 2: Run to verify fails

```bash
pytest tests/backend/test_ai_service.py -v
```

### Step 3: Implement ai_service.py

```python
# backend/services/ai_service.py
"""
ai_service — segment slicing, provider dispatch, and seamless splice.

Post-processing pipeline (each step is a standalone pure function):
  resample_audio()   — normalize sample rate
  rms_normalize()    — match loudness to original
  crossfade_edges()  — smooth splice boundaries using adjacent audio
  match_duration()   — optional: force exact original length

splice_segment() composes these steps; each can be individually disabled.
"""
import io
from pathlib import Path
from typing import Literal
import numpy as np
import soundfile as sf
import librosa
from ..config import StaticConfig
from ..providers.base import AIProvider

SR = StaticConfig.INTERNAL_SAMPLE_RATE


# ── private I/O helpers ──────────────────────────────────────────────────────

def _bytes_to_array(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """WAV bytes → (mono float32 numpy array, sample_rate)."""
    audio, sr = sf.read(io.BytesIO(wav_bytes), always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio.astype(np.float32), int(sr)


def _array_to_bytes(audio: np.ndarray, sr: int) -> bytes:
    """numpy array → WAV bytes at given sample rate."""
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


# ── public post-processing steps (pure functions) ────────────────────────────

def resample_audio(audio: np.ndarray, src_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample audio from src_sr to target_sr.

    Input:  float32 mono array at src_sr
    Output: float32 mono array at target_sr (same values if src_sr == target_sr)
    """
    if src_sr == target_sr:
        return audio.astype(np.float32)
    return librosa.resample(audio.astype(np.float32), orig_sr=src_sr, target_sr=target_sr)


def rms_normalize(modified: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Scale modified so its RMS loudness matches reference's RMS.
    Output is clipped to [-1.0, 1.0].

    Input:  modified — float32 array to scale
            reference — float32 array whose RMS to match
    Output: float32 array at same RMS as reference, clipped
    """
    ref_rms = np.sqrt(np.mean(reference ** 2)) + 1e-9
    mod_rms = np.sqrt(np.mean(modified ** 2)) + 1e-9
    scaled = modified * (ref_rms / mod_rms)
    return np.clip(scaled, -1.0, 1.0).astype(np.float32)


def crossfade_edges(
    modified: np.ndarray,
    before: np.ndarray,
    after: np.ndarray,
    crossfade_samples: int,
) -> np.ndarray:
    """
    Blend the start and end of modified with the adjacent before/after audio.

    At the START boundary: modified[0] → 0 (AI fades in over crossfade_samples).
                           before[-crossfade_samples:] → 1 (original fades out).
    At the END boundary:   modified[-1] → 0 (AI fades out).
                           after[:crossfade_samples] → 1 (original fades back in).

    This works regardless of whether modified is shorter or longer than the original segment.

    Input:  modified — float32 array (AI output, already at INTERNAL_SAMPLE_RATE)
            before   — float32 array of audio immediately before the splice (must be ≥ crossfade_samples long)
            after    — float32 array of audio immediately after the splice (must be ≥ crossfade_samples long)
            crossfade_samples — number of samples to blend (0 = no crossfade)
    Output: float32 array, same length as modified, with faded edges
    """
    if crossfade_samples <= 0:
        return modified.copy()

    result = modified.copy()
    cf = min(crossfade_samples, len(modified) // 4, len(before), len(after))
    if cf <= 0:
        return result

    fade_in  = np.linspace(0.0, 1.0, cf, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, cf, dtype=np.float32)

    # START: blend before[-cf:] (fading out) into result[:cf] (fading in)
    result[:cf] = result[:cf] * fade_in + before[-cf:] * fade_out

    # END: blend result[-cf:] (fading out) into after[:cf] (fading in)
    result[-cf:] = result[-cf:] * fade_out + after[:cf] * fade_in

    return result


def match_duration(modified: np.ndarray, target_samples: int) -> np.ndarray:
    """
    Trim or pad modified to exactly target_samples.
    Padding uses silence (zeros) at the end.

    Input:  modified — float32 array of any length
            target_samples — desired output length in samples
    Output: float32 array of length exactly target_samples
    """
    if len(modified) > target_samples:
        return modified[:target_samples]
    if len(modified) < target_samples:
        pad = np.zeros(target_samples - len(modified), dtype=np.float32)
        return np.concatenate([modified, pad])
    return modified


# ── splice_segment: compose the post-processing pipeline ────────────────────

def splice_segment(
    wav_path: Path,
    start_sec: float,
    end_sec: float,
    modified_wav: bytes,
    *,
    force_duration_match: bool = False,
    normalize_loudness: bool = True,
    crossfade_ms: int = StaticConfig.SPLICE_CROSSFADE_MS,
) -> bytes:
    """
    Splice modified_wav into wav_path, replacing [start_sec, end_sec].

    Args:
        wav_path:          path to the full original track WAV
        start_sec:         start of the region to replace (seconds)
        end_sec:           end of the region to replace (seconds)
        modified_wav:      AI provider output as WAV bytes (any sample rate)

    Keyword-only options (all independently toggleable):
        force_duration_match: False (default) = keep AI output at its natural length;
                              total track length will differ if AI output duration differs.
                              True = trim/pad AI output to exactly match original segment length.
        normalize_loudness:   True (default) = scale AI output RMS to match original segment RMS.
        crossfade_ms:         ms to crossfade at each boundary (default from StaticConfig).
                              Set to 0 to disable crossfade entirely.

    Returns: complete spliced track as WAV bytes at INTERNAL_SAMPLE_RATE.
    """
    # Load full track at its stored rate, resample to INTERNAL_SAMPLE_RATE
    original, src_sr = sf.read(str(wav_path), always_2d=False)
    if original.ndim == 2:
        original = original.mean(axis=1)
    original = resample_audio(original.astype(np.float32), src_sr, SR)

    start_idx = int(start_sec * SR)
    end_idx   = min(int(end_sec * SR), len(original))

    before           = original[:start_idx]
    original_segment = original[start_idx:end_idx]
    after            = original[end_idx:]

    # Step 1: resample provider output to INTERNAL_SAMPLE_RATE
    mod_array, mod_sr = _bytes_to_array(modified_wav)
    mod_array = resample_audio(mod_array, mod_sr, SR)

    # Step 2 (optional): force exact original segment length
    if force_duration_match:
        mod_array = match_duration(mod_array, target_samples=len(original_segment))

    # Step 3 (optional): match loudness to original segment
    if normalize_loudness:
        mod_array = rms_normalize(mod_array, reference=original_segment)

    # Step 4 (optional): crossfade at both splice boundaries
    cf_samples = int(SR * crossfade_ms / 1000)
    mod_array = crossfade_edges(mod_array, before=before, after=after, crossfade_samples=cf_samples)

    # Assemble: before + AI output + after
    result = np.concatenate([before, mod_array, after])
    return _array_to_bytes(result, SR)


# ── slice_segment ────────────────────────────────────────────────────────────

def slice_segment(wav_path: Path, start_sec: float, end_sec: float) -> tuple[bytes, float]:
    """
    Extract [start_sec, end_sec] from a WAV file.

    Input:  wav_path — path to WAV file (any sample rate)
            start_sec, end_sec — region to extract in seconds
    Output: (segment_wav_bytes at INTERNAL_SAMPLE_RATE, duration_sec)

    Raises:
        ValueError: if start_sec >= end_sec or end_sec > track duration
    """
    if start_sec >= end_sec:
        raise ValueError(f"start_sec must be less than end_sec, got {start_sec} >= {end_sec}")

    audio, sr = sf.read(str(wav_path), always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)

    total_sec = len(audio) / sr
    if end_sec > total_sec + 0.01:
        raise ValueError(f"end_sec {end_sec:.2f}s out of range for track of {total_sec:.2f}s")

    start_idx = int(start_sec * sr)
    end_idx   = min(int(end_sec * sr), len(audio))
    segment   = audio[start_idx:end_idx]

    segment = resample_audio(segment, src_sr=sr, target_sr=SR)
    return _array_to_bytes(segment, SR), len(segment) / SR


# ── build_prompt ─────────────────────────────────────────────────────────────

def build_prompt(mode: Literal["style", "melody", "accompaniment"], user_prompt: str) -> str:
    """
    Prepend a mode-specific instruction to the user's text prompt.

    Input:  mode — one of "style", "melody", "accompaniment"
            user_prompt — free-text from the user
    Output: enriched prompt string sent to the AI provider
    """
    prefixes = {
        "style": "Style transfer — transform the genre/feel of this musical segment while preserving its melody. ",
        "melody": "Melody variation — create a new melodic variation on this segment's theme. ",
        "accompaniment": "Accompaniment generation — generate a harmonic accompaniment for this melody. ",
    }
    return prefixes[mode] + user_prompt


# ── get_provider factory ─────────────────────────────────────────────────────

def get_provider(name: Literal["local", "replicate"]) -> AIProvider:
    """
    Return an AIProvider instance by name.
    Imports are deferred so torch is only loaded when actually needed.
    """
    if name == "local":
        from ..providers.musicgen import MusicGenProvider
        return MusicGenProvider()
    from ..providers.replicate_provider import ReplicateProvider
    return ReplicateProvider()


# ── dispatch ─────────────────────────────────────────────────────────────────

async def dispatch(
    provider: AIProvider,
    wav_path: Path,
    start_sec: float,
    end_sec: float,
    mode: Literal["style", "melody", "accompaniment"],
    prompt: str,
) -> bytes:
    """
    Slice the segment, enrich the prompt, call provider.modify(), return raw WAV bytes.

    Note: this does NOT splice the result back into the track.
    Call splice_segment() separately after reviewing the provider output.

    Input:  provider — AIProvider instance
            wav_path — full track WAV path
            start_sec, end_sec — region to modify
            mode, prompt — modification instructions
    Output: provider output as WAV bytes at INTERNAL_SAMPLE_RATE (unspliced)
    """
    segment_bytes, duration_sec = slice_segment(wav_path, start_sec, end_sec)
    full_prompt = build_prompt(mode, prompt)
    return await provider.modify(
        segment_audio=segment_bytes,
        segment_duration_sec=duration_sec,
        mode=mode,
        prompt=full_prompt,
    )
```

### Step 4: Run to verify passes

```bash
pytest tests/backend/test_ai_service.py -v
```

Expected: all pass (20+ tests).

### Step 5: Commit

```bash
git add backend/services/ai_service.py tests/backend/test_ai_service.py
git commit -m "feat: ai_service — decoupled splice pipeline (resample/normalize/crossfade/match_duration)"
```

---

## Task 5: MusicGen-Melody Provider (Local GPU)

**Files:**
- Create: `backend/providers/musicgen.py`
- Create: `tests/backend/test_musicgen_provider.py`

**How it works:** `MusicgenMelodyForConditionalGeneration` accepts both a text prompt and an audio array as melody conditioning. The model generates audio that follows the melodic contour of `segment_audio` while applying the requested style. Output is resampled from the model's native 32000 Hz to `INTERNAL_SAMPLE_RATE`.

### Step 1: Write contract test (mocked inference — no real GPU in CI)

```python
# tests/backend/test_musicgen_provider.py
import io
import numpy as np
import soundfile as sf
import pytest
from unittest.mock import patch, MagicMock
from backend.config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE
MODEL_SR = 32000  # MusicGen-Melody's native output rate


def _make_wav(duration_sec: float, sr: int = SR) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_musicgen_provider_returns_wav_at_internal_rate():
    """Provider must return WAV bytes at INTERNAL_SAMPLE_RATE."""
    from backend.providers.musicgen import MusicGenProvider

    # Simulate model output: 5s at 32000 Hz (model native rate)
    fake_audio_32k = np.zeros(int(MODEL_SR * 5), dtype=np.float32)
    # shape: [batch=1, channels=1, samples]
    fake_tensor = MagicMock()
    fake_tensor.cpu.return_value.numpy.return_value = fake_audio_32k[np.newaxis, np.newaxis, :]

    with patch("backend.providers.musicgen._load_model") as mock_load:
        mock_processor = MagicMock()
        mock_model = MagicMock()
        # Processor returns inputs dict
        mock_processor.return_value = {"input_ids": MagicMock(), "input_features": MagicMock()}
        # Model.generate returns audio_values tensor
        mock_model.generate.return_value = fake_tensor
        mock_model.config.audio_encoder.sampling_rate = MODEL_SR
        mock_load.return_value = (mock_processor, mock_model)

        provider = MusicGenProvider()
        result = await provider.modify(
            segment_audio=_make_wav(5.0),
            segment_duration_sec=5.0,
            mode="style",
            prompt="make it jazzy",
        )

    assert isinstance(result, bytes)
    audio, sr = sf.read(io.BytesIO(result))
    assert sr == SR
    assert len(audio) > 0


@pytest.mark.asyncio
async def test_musicgen_provider_satisfies_abc():
    """Provider class must be a concrete implementation of AIProvider."""
    from backend.providers.musicgen import MusicGenProvider
    from backend.providers.base import AIProvider
    assert issubclass(MusicGenProvider, AIProvider)
```

### Step 2: Run to verify fails

```bash
pytest tests/backend/test_musicgen_provider.py -v
```

### Step 3: Implement

```python
# backend/providers/musicgen.py
"""
MusicGen-Melody provider for local GPU inference.

Model: facebook/musicgen-melody
- Accepts text prompt + audio melody conditioning.
- Outputs audio at 32000 Hz; we resample to INTERNAL_SAMPLE_RATE before returning.
- Model is cached in memory after first load (lru_cache) to avoid reload overhead.
"""
import io
from functools import lru_cache
from typing import Literal
import numpy as np
import soundfile as sf
import librosa
from .base import AIProvider
from ..config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE


@lru_cache(maxsize=1)
def _load_model():
    """Load processor and model once; cache for the process lifetime."""
    from transformers import AutoProcessor, MusicgenMelodyForConditionalGeneration
    processor = AutoProcessor.from_pretrained("facebook/musicgen-melody")
    model = MusicgenMelodyForConditionalGeneration.from_pretrained("facebook/musicgen-melody")
    try:
        model = model.to("cuda")
    except Exception:
        pass  # fall back to CPU — slow but functional
    return processor, model


class MusicGenProvider(AIProvider):
    async def modify(
        self,
        segment_audio: bytes,
        segment_duration_sec: float,
        mode: Literal["style", "melody", "accompaniment"],
        prompt: str,
    ) -> bytes:
        """
        Generate audio conditioned on segment_audio melody + text prompt.

        Returns WAV bytes at INTERNAL_SAMPLE_RATE (22050 Hz).
        """
        processor, model = _load_model()
        model_sr: int = model.config.audio_encoder.sampling_rate  # typically 32000

        # Decode segment to float array for melody conditioning
        seg_array, seg_sr = sf.read(io.BytesIO(segment_audio), always_2d=False)
        if seg_array.ndim == 2:
            seg_array = seg_array.mean(axis=1)
        # Resample to model's expected audio rate if needed
        if seg_sr != model_sr:
            seg_array = librosa.resample(
                seg_array.astype(np.float32), orig_sr=seg_sr, target_sr=model_sr
            )
        seg_array = seg_array.astype(np.float32)

        # max_new_tokens: model generates ~50 tokens/sec
        max_tokens = max(50, int(segment_duration_sec * 51.2))

        inputs = processor(
            text=[prompt],
            audio=seg_array,
            sampling_rate=model_sr,
            return_tensors="pt",
        )

        import torch
        device = next(model.parameters()).device
        inputs = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}

        with torch.no_grad():
            audio_values = model.generate(**inputs, max_new_tokens=max_tokens)

        # audio_values shape: [batch, channels, samples] — take first batch, average channels
        generated = audio_values[0].cpu().numpy()
        if generated.ndim == 2:
            generated = generated.mean(axis=0)
        generated = generated.astype(np.float32)

        # Resample from model native rate to INTERNAL_SAMPLE_RATE
        if model_sr != SR:
            generated = librosa.resample(generated, orig_sr=model_sr, target_sr=SR)

        buf = io.BytesIO()
        sf.write(buf, generated, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
```

### Step 4: Run to verify passes

```bash
pytest tests/backend/test_musicgen_provider.py -v
```

### Step 5: Commit

```bash
git add backend/providers/musicgen.py tests/backend/test_musicgen_provider.py
git commit -m "feat: MusicGenProvider — musicgen-melody with audio conditioning, 22050 Hz output"
```

---

## Task 6: Replicate Provider

**Files:**
- Create: `backend/providers/replicate_provider.py`
- Create: `tests/backend/test_replicate_provider.py`

**How it works:** Uses `meta/musicgen` on Replicate with `model_version: "melody"`. The `segment_audio` bytes are encoded as a `data:audio/wav;base64,...` URI and passed as `input_audio`. Replicate returns a WAV URL; we download it, resample to 22050 Hz, and return WAV bytes.

### Step 1: Write contract test (mocked HTTP)

```python
# tests/backend/test_replicate_provider.py
import io
import base64
import numpy as np
import soundfile as sf
import pytest
from unittest.mock import patch, MagicMock
from backend.config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE


def _make_wav(duration_sec: float, sr: int = SR) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_replicate_provider_returns_wav_at_internal_rate():
    from backend.providers.replicate_provider import ReplicateProvider

    # Simulate Replicate returning a WAV at 32000 Hz (arbitrary provider rate)
    fake_output_32k = _make_wav(5.0, sr=32000)

    with patch("backend.providers.replicate_provider.replicate") as mock_replicate, \
         patch("backend.providers.replicate_provider._download_bytes") as mock_dl:
        mock_replicate.run = MagicMock(return_value="https://fake-replicate-url/output.wav")
        mock_dl.return_value = fake_output_32k

        provider = ReplicateProvider()
        result = await provider.modify(
            segment_audio=_make_wav(5.0),
            segment_duration_sec=5.0,
            mode="style",
            prompt="make it jazzy",
        )

    assert isinstance(result, bytes)
    audio, sr = sf.read(io.BytesIO(result))
    assert sr == SR
    assert len(audio) > 0


@pytest.mark.asyncio
async def test_replicate_provider_passes_input_audio():
    """Ensure the provider encodes segment_audio as data URI in the Replicate call."""
    from backend.providers.replicate_provider import ReplicateProvider

    segment = _make_wav(5.0)
    captured_input = {}

    def fake_run(model, input):
        captured_input.update(input)
        return _make_wav(5.0, sr=32000)

    with patch("backend.providers.replicate_provider.replicate") as mock_replicate, \
         patch("backend.providers.replicate_provider._download_bytes", return_value=_make_wav(5.0)):
        mock_replicate.run = fake_run
        provider = ReplicateProvider()
        await provider.modify(
            segment_audio=segment,
            segment_duration_sec=5.0,
            mode="melody",
            prompt="vary the melody",
        )

    assert "input_audio" in captured_input
    assert captured_input["input_audio"].startswith("data:audio/wav;base64,")
```

### Step 2: Run to verify fails

```bash
pytest tests/backend/test_replicate_provider.py -v
```

### Step 3: Implement

```python
# backend/providers/replicate_provider.py
"""
Replicate provider using meta/musicgen with melody conditioning.

segment_audio is sent as a data URI (base64-encoded WAV) so Replicate
can use it as the melody input without requiring a separate file upload.
"""
import io
import os
import base64
from typing import Literal
import httpx
import replicate
import soundfile as sf
import librosa
import numpy as np
from .base import AIProvider
from ..config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE

# Replicate musicgen model — use the melody variant
_MODEL = "meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb"


def _download_bytes(url: str) -> bytes:
    """Download audio bytes from a URL (Replicate output URL)."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


class ReplicateProvider(AIProvider):
    async def modify(
        self,
        segment_audio: bytes,
        segment_duration_sec: float,
        mode: Literal["style", "melody", "accompaniment"],
        prompt: str,
    ) -> bytes:
        token = os.environ.get("REPLICATE_API_TOKEN", StaticConfig.REPLICATE_API_TOKEN)
        if not token:
            raise ValueError("REPLICATE_API_TOKEN not set")

        # Encode segment WAV as a data URI for melody conditioning
        b64 = base64.b64encode(segment_audio).decode("ascii")
        input_audio_uri = f"data:audio/wav;base64,{b64}"

        duration = max(2, min(30, int(segment_duration_sec) + 1))

        output = replicate.run(
            _MODEL,
            input={
                "prompt": prompt,
                "input_audio": input_audio_uri,
                "duration": duration,
                "model_version": "melody",
                "output_format": "wav",
                "normalization_strategy": "peak",
            },
        )

        # Replicate returns a URL string for the output file
        if isinstance(output, str):
            raw_bytes = _download_bytes(output)
        elif hasattr(output, "read"):
            raw_bytes = output.read()
        else:
            # Iterator of chunks
            raw_bytes = b"".join(list(output))

        # Resample to INTERNAL_SAMPLE_RATE
        audio, src_sr = sf.read(io.BytesIO(raw_bytes), always_2d=False)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        audio = audio.astype(np.float32)
        if src_sr != SR:
            audio = librosa.resample(audio, orig_sr=src_sr, target_sr=SR)

        buf = io.BytesIO()
        sf.write(buf, audio, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
```

### Step 4: Run to verify passes

```bash
pytest tests/backend/test_replicate_provider.py -v
```

### Step 5: Commit

```bash
git add backend/providers/replicate_provider.py tests/backend/test_replicate_provider.py
git commit -m "feat: ReplicateProvider — musicgen-melody via Replicate, data URI for melody conditioning"
```

---

## Task 7: AI Routes (Async Jobs + Splice Endpoint)

**Files:**
- Create: `backend/api/routes/ai.py`
- Modify: `backend/main.py` (register router, add startup recovery)
- Modify: `tests/backend/test_routes.py`

### Provider factory

Provider instantiation lives in `ai_service`, not in route handlers:

```python
# backend/services/ai_service.py — add this function
from typing import Literal
from ..providers.base import AIProvider

def get_provider(name: Literal["local", "replicate"]) -> AIProvider:
    if name == "local":
        from ..providers.musicgen import MusicGenProvider
        return MusicGenProvider()
    from ..providers.replicate_provider import ReplicateProvider
    return ReplicateProvider()
```

### Step 1: Write failing tests

```python
# append to tests/backend/test_routes.py

@pytest.mark.anyio
async def test_ai_modify_returns_job_id(client, wav_bytes):
    upload = await client.post("/audio/upload", files={"file": ("t.wav", wav_bytes, "audio/wav")})
    tid = upload.json()["track_id"]
    await client.post(f"/midi/{tid}/extract")

    resp = await client.post(f"/ai/{tid}/modify", json={
        "mode": "style",
        "prompt": "make it jazzy",
        "start_sec": 0.0,
        "end_sec": 1.0,
        "provider": "local",
    })
    assert resp.status_code == 200
    assert "job_id" in resp.json()


@pytest.mark.anyio
async def test_ai_modify_invalid_region_returns_422(client, wav_bytes):
    upload = await client.post("/audio/upload", files={"file": ("t.wav", wav_bytes, "audio/wav")})
    tid = upload.json()["track_id"]
    resp = await client.post(f"/ai/{tid}/modify", json={
        "mode": "style", "prompt": "test",
        "start_sec": 5.0, "end_sec": 2.0,  # invalid: start > end
        "provider": "local",
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ai_job_status_reachable(client, wav_bytes):
    upload = await client.post("/audio/upload", files={"file": ("t.wav", wav_bytes, "audio/wav")})
    tid = upload.json()["track_id"]
    await client.post(f"/midi/{tid}/extract")

    modify = await client.post(f"/ai/{tid}/modify", json={
        "mode": "melody", "prompt": "test", "start_sec": 0.0, "end_sec": 1.0, "provider": "local",
    })
    job_id = modify.json()["job_id"]
    resp = await client.get(f"/ai/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("pending", "running", "done", "failed")


@pytest.mark.anyio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

### Step 2: Run to verify fails

```bash
pytest tests/backend/test_routes.py::test_ai_modify_returns_job_id \
       tests/backend/test_routes.py::test_health_endpoint -v
```

### Step 3: Implement ai routes

```python
# backend/api/routes/ai.py
"""
AI modification routes.

POST /ai/{track_id}/modify   — submit async job
GET  /ai/jobs/{job_id}       — poll job status
GET  /ai/{track_id}/compare  — original vs AI segment URLs
POST /ai/{track_id}/splice   — splice AI output into full track
GET  /ai/jobs/{job_id}/result — stream AI output WAV
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, model_validator
from ..config import StaticConfig
from ..models.schemas import AIJob
from ..services.ai_service import dispatch, splice_segment, get_provider
from ..repositories.file_repo import FileRepo

router = APIRouter(prefix="/ai", tags=["ai"])
_repo = FileRepo()


class ModifyRequest(BaseModel):
    mode: Literal["style", "melody", "accompaniment"]
    prompt: str
    start_sec: float
    end_sec: float
    provider: Literal["local", "replicate"] = "local"

    @model_validator(mode="after")
    def validate_region(self):
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        return self


class SpliceRequest(BaseModel):
    job_id: str
    force_duration_match: bool = False   # True = trim/pad AI output to exact original length


def _job_path(job_id: str) -> Path:
    StaticConfig.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return StaticConfig.JOBS_DIR / f"{job_id}.json"


def _result_path(job_id: str) -> Path:
    return StaticConfig.JOBS_DIR / f"{job_id}_result.wav"


async def _run_job(job: AIJob, wav_path: Path) -> None:
    """Background task: run provider inference and write result to disk."""
    job_path = _job_path(str(job.id))
    try:
        job.status = "running"
        job_path.write_text(job.model_dump_json())

        provider = get_provider(job.provider)
        result_bytes = await dispatch(
            provider=provider,
            wav_path=wav_path,
            start_sec=job.start_sec,
            end_sec=job.end_sec,
            mode=job.mode,
            prompt=job.prompt,
        )
        _result_path(str(job.id)).write_bytes(result_bytes)
        job.status = "done"
        job.result_path = str(_result_path(str(job.id)))
    except Exception as exc:
        job.status = "failed"
        job.error_msg = str(exc)
    finally:
        job.updated_at = datetime.now(timezone.utc)
        job_path.write_text(job.model_dump_json())


@router.post("/{track_id}/modify")
async def modify(track_id: str, req: ModifyRequest, background_tasks: BackgroundTasks):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, detail=f"Track not found: {track_id}")

    # Validate region against track duration
    track = await _repo.get_track(track_id)
    if req.end_sec > track.duration_sec + 0.01:
        raise HTTPException(
            422,
            detail=f"end_sec {req.end_sec}s exceeds track duration {track.duration_sec:.2f}s",
        )

    job = AIJob(
        track_id=uuid.UUID(track_id),
        mode=req.mode,
        prompt=req.prompt,
        provider=req.provider,
        start_sec=req.start_sec,
        end_sec=req.end_sec,
    )
    _job_path(str(job.id)).write_text(job.model_dump_json())
    background_tasks.add_task(_run_job, job, wav_path)
    return {"job_id": str(job.id)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    path = _job_path(job_id)
    if not path.exists():
        raise HTTPException(404, detail=f"Job not found: {job_id}")
    return AIJob.model_validate_json(path.read_text()).model_dump(mode="json")


@router.get("/jobs/{job_id}/result")
async def get_result(job_id: str):
    path = _result_path(job_id)
    if not path.exists():
        raise HTTPException(404, detail="Job result not ready — job may still be running")
    return StreamingResponse(open(path, "rb"), media_type="audio/wav")


@router.get("/{track_id}/compare")
async def compare(track_id: str, job_id: str):
    result = _result_path(job_id)
    if not result.exists():
        raise HTTPException(404, detail="Job result not ready — job may still be running")
    return {
        "original_url": f"/audio/{track_id}/playback",
        "modified_url": f"/ai/jobs/{job_id}/result",
    }


@router.post("/{track_id}/splice")
async def splice(track_id: str, req: SpliceRequest):
    """Splice AI-modified segment back into full track. Returns new track_id."""
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, detail=f"Track not found: {track_id}")

    job_path = _job_path(req.job_id)
    if not job_path.exists():
        raise HTTPException(404, detail=f"Job not found: {req.job_id}")

    job = AIJob.model_validate_json(job_path.read_text())
    if job.status != "done":
        raise HTTPException(409, detail=f"Job not done (status='{job.status}'). Wait for completion.")

    result_path = _result_path(req.job_id)
    modified_wav = result_path.read_bytes()

    spliced_bytes = splice_segment(
        wav_path=wav_path,
        start_sec=job.start_sec,
        end_sec=job.end_sec,
        modified_wav=modified_wav,
        force_duration_match=req.force_duration_match,
    )

    # Save as new track
    new_track_id = str(uuid4())
    new_path = StaticConfig.AUDIO_DIR / f"{new_track_id}.wav"
    new_path.write_bytes(spliced_bytes)

    # Persist job's spliced_track_id
    job.spliced_track_id = new_track_id
    job_path.write_text(job.model_dump_json())

    return {"spliced_track_id": new_track_id}
```

### Step 4: Register router and add startup recovery in main.py

```python
# backend/main.py — add startup event for stale job recovery:
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pathlib import Path
from .config import StaticConfig
from .models.schemas import AIJob
from .api.routes import audio, midi, ai as ai_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: reset any stale "running" jobs to "failed"
    jobs_dir = StaticConfig.JOBS_DIR
    if jobs_dir.exists():
        for job_file in jobs_dir.glob("*.json"):
            try:
                job = AIJob.model_validate_json(job_file.read_text())
                if job.status == "running":
                    job.status = "failed"
                    job.error_msg = "Server restarted"
                    job_file.write_text(job.model_dump_json())
            except Exception:
                pass  # corrupt file — ignore
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(audio.router)
app.include_router(midi.router)
app.include_router(ai_routes.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

### Step 5: Run to verify passes

```bash
pytest tests/backend/test_routes.py -v
```

Expected: all pass.

### Step 6: Commit

```bash
git add backend/api/routes/ai.py backend/main.py tests/backend/test_routes.py
git commit -m "feat: AI routes — modify, job poll, compare, splice; startup stale job recovery"
```

---

## Task 8: Frontend — AI Modification Page

**Files:**
- Modify: `frontend/api_client.py`
- Create: `frontend/pages/ai_modify.py`
- Modify: `frontend/app.py`

### Step 1: Add AI methods to api_client.py

```python
# append to frontend/api_client.py
import time

def request_ai_modify(
    track_id: str, mode: str, prompt: str,
    start_sec: float, end_sec: float, provider: str
) -> str:
    resp = _client.post(f"/ai/{track_id}/modify", json={
        "mode": mode, "prompt": prompt,
        "start_sec": start_sec, "end_sec": end_sec, "provider": provider,
    }, timeout=10.0)
    resp.raise_for_status()
    return resp.json()["job_id"]


def poll_job(job_id: str) -> dict:
    resp = _client.get(f"/ai/jobs/{job_id}")
    resp.raise_for_status()
    return resp.json()


def splice_ai_result(track_id: str, job_id: str, force_duration_match: bool = False) -> str:
    """Splice AI output into full track. Returns new spliced_track_id."""
    resp = _client.post(
        f"/ai/{track_id}/splice",
        json={"job_id": job_id, "force_duration_match": force_duration_match},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["spliced_track_id"]


def get_ai_result_url(job_id: str) -> str:
    return f"{BACKEND_URL}/ai/jobs/{job_id}/result"


def get_playback_url(track_id: str) -> str:
    return f"{BACKEND_URL}/audio/{track_id}/playback"
```

### Step 2: Create ai_modify page

```python
# frontend/pages/ai_modify.py
"""
AI Modification tab.

Flow:
  1. User selects region (start/end seconds), mode, provider, and prompt.
  2. Click "Generate" → POST /ai/{track_id}/modify → poll until done.
  3. Compare: toggle between original and AI segment.
  4. "Apply to Track" → POST /ai/{track_id}/splice → load spliced track for editing.
"""
import time
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import api_client

MODES = {
    "Style Transfer": "style",
    "Melody Variation": "melody",
    "Accompaniment": "accompaniment",
}


def render():
    st.header("AI Modification")
    track_id = st.session_state.get("track_id")
    if not track_id:
        st.info("Upload or record a track first.")
        return

    # Sidebar: provider toggle
    provider = "local" if st.sidebar.toggle("Use Local GPU (MusicGen)", value=True) else "replicate"
    st.sidebar.caption("Local: free, GPU recommended. Replicate: ~$0.07/call, no GPU needed.")

    mode_label = st.radio("Modification Mode", list(MODES.keys()), horizontal=True)
    mode = MODES[mode_label]

    col1, col2 = st.columns(2)
    with col1:
        start_sec = st.number_input("Segment start (s)", 0.0, value=0.0, step=0.1)
    with col2:
        end_sec = st.number_input("Segment end (s)", 0.0, value=5.0, step=0.1)

    if start_sec >= end_sec:
        st.warning("Start must be less than end.")
        return

    prompt = st.text_input("Prompt", placeholder="e.g. make it jazzy, add blues feeling...")

    if st.button("Generate AI Version", disabled=not prompt.strip()):
        with st.spinner(f"Queuing {mode_label} job ({provider})..."):
            try:
                job_id = api_client.request_ai_modify(
                    track_id, mode, prompt, start_sec, end_sec, provider
                )
                st.session_state["last_job_id"] = job_id
                st.session_state["last_job_start"] = start_sec
                st.session_state["last_job_end"] = end_sec
            except Exception as exc:
                st.error(f"Failed to start job: {exc}")
                return

        # Poll until done (max 5 minutes)
        status_ph = st.empty()
        for _ in range(150):
            job = api_client.poll_job(job_id)
            status_ph.caption(f"Job status: **{job['status']}**")
            if job["status"] == "done":
                st.success("Generation complete!")
                break
            if job["status"] == "failed":
                st.error(f"Job failed: {job.get('error_msg', 'unknown error')}")
                return
            time.sleep(2)
        else:
            st.warning("Timed out waiting for job. Refresh to check status.")

    # Comparison toggle
    job_id = st.session_state.get("last_job_id")
    if job_id:
        job = api_client.poll_job(job_id)
        if job["status"] == "done":
            st.subheader("Compare")
            show_modified = st.toggle("AI version", value=True)
            if show_modified:
                st.caption("AI Modified Segment")
                st.audio(api_client.get_ai_result_url(job_id))
            else:
                st.caption("Original Playback")
                st.audio(api_client.get_playback_url(track_id))

            force_match = st.checkbox("Force exact original length (trim/pad AI output)", value=False)
            if st.button("Apply to Track (splice AI into full track)"):
                with st.spinner("Splicing..."):
                    try:
                        spliced_id = api_client.splice_ai_result(track_id, job_id, force_duration_match=force_match)
                        st.session_state["track_id"] = spliced_id
                        st.success(f"Applied! New track id: {spliced_id}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Splice failed: {exc}")
```

### Step 3: Add AI tab to app.py

```python
# frontend/app.py
import streamlit as st

st.set_page_config(page_title="AI Music", layout="wide")
st.title("AI Music")

with st.sidebar:
    st.header("Settings")

tab_record, tab_upload, tab_editor, tab_ai = st.tabs(["Record", "Upload", "Editor", "AI Modify"])

with tab_record:
    from pages.record import render; render()
with tab_upload:
    from pages.upload import render; render()
with tab_editor:
    from pages.editor import render; render()
with tab_ai:
    from pages.ai_modify import render; render()
```

### Step 4: Manual end-to-end test

```bash
scripts/ctl restart
```
1. Upload a 10-15s track, extract MIDI
2. Go to "AI Modify" tab
3. Set region 0–5s, mode "Style Transfer", prompt "make it jazzy", Local GPU
4. Click Generate — spinner polls until "done"
5. Toggle between original and AI version — both should play audio
6. Click "Apply to Track" — verify page reloads with new track_id

### Step 5: Commit

```bash
git add frontend/api_client.py frontend/pages/ai_modify.py frontend/app.py
git commit -m "feat: AI modification tab — generate, compare, and splice into full track"
```

---

## Task 9: Extend Integration Test

**Files:**
- Modify: `scripts/run_integration_test.sh`

```bash
# append before final echo in run_integration_test.sh

echo "[7/7] AI modify job (checks routing + stale recovery)..."
# Submit job
JOB_RESP=$(curl -sf -X POST "$BACKEND/ai/$TRACK_ID/modify" \
  -H "Content-Type: application/json" \
  -d "{\"mode\":\"style\",\"prompt\":\"test\",\"start_sec\":0.0,\"end_sec\":1.0,\"provider\":\"local\"}")
JOB_ID=$(echo "$JOB_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
JOB_STATUS=$(curl -sf "$BACKEND/ai/jobs/$JOB_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
[[ "$JOB_STATUS" =~ ^(pending|running|done|failed)$ ]] || { echo "FAIL — unexpected status: $JOB_STATUS"; exit 1; }
echo "      PASS — job $JOB_ID status=$JOB_STATUS"

echo "[8/8] Health check..."
HEALTH=$(curl -sf "$BACKEND/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
[[ "$HEALTH" == "ok" ]] || { echo "FAIL — health check returned: $HEALTH"; exit 1; }
echo "      PASS — health ok"
```

```bash
scripts/ctl test integration
```

Expected: 8/8 PASS.

```bash
git add scripts/run_integration_test.sh
git commit -m "test: extend integration test to cover AI modify routing and health endpoint"
```

---

## Phase 4 Complete Checklist

- [ ] `ctl test unit` — all pass (providers and ai_service tested with mocks)
- [ ] `ctl test integration` — 8/8 pass
- [ ] MusicGen-Melody local provider: segment audio plays as melody conditioning (manual test)
- [ ] Replicate provider: verify `input_audio` data URI is in the Replicate request (mock test)
- [ ] All three modes (style, melody, accompaniment) return non-empty audio
- [ ] Spliced track plays seamlessly — no click or volume jump at splice boundaries
- [ ] Stale job recovery: start server with a `running` job on disk → job becomes `failed` after restart
- [ ] Toggle shows original vs AI segment
- [ ] "Apply to Track" creates new track_id and updates editor state
- [ ] Local/Replicate sidebar toggle switches provider in real-time

## Seamless Splice Verification (Manual)

To confirm there are no audible clicks at splice boundaries:
1. Upload a 30s track with consistent content (e.g., a drone or repeating chord)
2. Select region 10–15s, generate AI version
3. Apply splice
4. Play spliced track continuously — the transition at 10s and 15s should be smooth
5. If click is audible, increase `SPLICE_CROSSFADE_MS` in StaticConfig (default 80ms, try 150ms)
