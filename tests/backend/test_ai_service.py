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


# resample_audio
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


# rms_normalize
def test_rms_normalize_matches_reference_loudness():
    quiet = _make_array(1.0, amplitude=0.05)
    loud_ref = _make_array(1.0, amplitude=0.5)
    normalized = rms_normalize(quiet, reference=loud_ref)
    norm_rms = np.sqrt(np.mean(normalized ** 2))
    ref_rms = np.sqrt(np.mean(loud_ref ** 2))
    assert abs(norm_rms - ref_rms) < 0.01


def test_rms_normalize_clips_to_safe_range():
    audio = _make_array(1.0, amplitude=0.9)
    silent_ref = np.zeros(SR, dtype=np.float32)
    result = rms_normalize(audio, reference=silent_ref)
    assert np.all(np.abs(result) <= 1.0)


# crossfade_edges
def test_crossfade_edges_first_sample_matches_before():
    before = _make_array(5.0, freq=440.0)
    modified = _make_array(3.0, freq=880.0)
    after = _make_array(5.0, freq=220.0)
    cf = int(SR * 0.08)
    result = crossfade_edges(modified, before=before, after=after, crossfade_samples=cf)
    assert abs(result[0] - before[-cf]) < 0.01


def test_crossfade_edges_last_sample_matches_after():
    before = _make_array(5.0, freq=440.0)
    modified = _make_array(3.0, freq=880.0)
    after = _make_array(5.0, freq=220.0)
    cf = int(SR * 0.08)
    result = crossfade_edges(modified, before=before, after=after, crossfade_samples=cf)
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


# match_duration
def test_match_duration_trims_longer_audio():
    audio = _make_array(6.0)
    result = match_duration(audio, target_samples=int(SR * 5.0))
    assert len(result) == int(SR * 5.0)


def test_match_duration_pads_shorter_audio_with_silence():
    audio = _make_array(3.0)
    target = int(SR * 5.0)
    result = match_duration(audio, target_samples=target)
    assert len(result) == target
    assert np.all(result[len(audio):] == 0.0)


# slice_segment
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
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(10.0, sr=44100))
    segment_bytes, _ = slice_segment(wav_path, start_sec=2.0, end_sec=5.0)
    _, sr = _read_wav(segment_bytes)
    assert sr == SR


# build_prompt
def test_build_prompt_style_contains_mode_and_user_text():
    prompt = build_prompt("style", "make it jazzy")
    assert "jazzy" in prompt
    assert "style" in prompt.lower() or "genre" in prompt.lower()


def test_build_prompt_accompaniment_contains_mode_and_user_text():
    prompt = build_prompt("accompaniment", "add bass line")
    assert "accompaniment" in prompt.lower() or "harmonic" in prompt.lower()
    assert "bass line" in prompt


# splice_segment
def test_splice_segment_default_keeps_ai_duration(tmp_path):
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0))
    modified_bytes = _make_wav(7.0, freq=880.0)
    spliced = splice_segment(wav_path, start_sec=5.0, end_sec=10.0, modified_wav=modified_bytes)
    spliced_audio, _ = _read_wav(spliced)
    assert abs(len(spliced_audio) / SR - 22.0) < 0.5


def test_splice_segment_force_duration_match_preserves_length(tmp_path):
    wav_path = tmp_path / "track.wav"
    original_bytes = _make_wav(20.0)
    wav_path.write_bytes(original_bytes)
    modified_bytes = _make_wav(7.0, freq=880.0)
    spliced = splice_segment(
        wav_path, start_sec=5.0, end_sec=10.0,
        modified_wav=modified_bytes,
        force_duration_match=True,
    )
    original_audio, _ = _read_wav(original_bytes)
    spliced_audio, _ = _read_wav(spliced)
    assert abs(len(spliced_audio) - len(original_audio)) < SR * 0.1


def test_splice_segment_modified_audio_has_energy(tmp_path):
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0, freq=440.0))
    modified_bytes = _make_wav(5.0, freq=880.0)
    spliced = splice_segment(wav_path, start_sec=5.0, end_sec=10.0, modified_wav=modified_bytes)
    spliced_audio, sr = _read_wav(spliced)
    region = spliced_audio[int(5.5 * sr) : int(9.5 * sr)]
    assert np.sqrt(np.mean(region ** 2)) > 0.001


def test_splice_segment_no_normalize_loudness(tmp_path):
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0, amplitude=0.1))
    modified_bytes = _make_wav(5.0, freq=880.0, amplitude=0.8)
    spliced = splice_segment(
        wav_path, start_sec=5.0, end_sec=10.0,
        modified_wav=modified_bytes,
        normalize_loudness=False,
    )
    spliced_audio, sr = _read_wav(spliced)
    region = spliced_audio[int(5.5 * sr) : int(9.5 * sr)]
    assert np.sqrt(np.mean(region ** 2)) > 0.3


def test_splice_segment_no_crossfade_still_works(tmp_path):
    wav_path = tmp_path / "track.wav"
    wav_path.write_bytes(_make_wav(20.0))
    modified_bytes = _make_wav(5.0, freq=880.0)
    spliced = splice_segment(
        wav_path, start_sec=5.0, end_sec=10.0,
        modified_wav=modified_bytes,
        crossfade_ms=0,
    )
    assert len(spliced) > 0


# dispatch
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
