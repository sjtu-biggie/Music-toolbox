"""
ai_service — segment slicing, provider dispatch, and seamless splice.
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


def _bytes_to_array(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(io.BytesIO(wav_bytes), always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio.astype(np.float32), int(sr)


def _array_to_bytes(audio: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def resample_audio(audio: np.ndarray, src_sr: int, target_sr: int) -> np.ndarray:
    if src_sr == target_sr:
        return audio.astype(np.float32)
    return librosa.resample(audio.astype(np.float32), orig_sr=src_sr, target_sr=target_sr)


def rms_normalize(modified: np.ndarray, reference: np.ndarray) -> np.ndarray:
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
    if crossfade_samples <= 0:
        return modified.copy()
    result = modified.copy()
    cf = min(crossfade_samples, len(modified) // 4, len(before), len(after))
    if cf <= 0:
        return result
    fade_in = np.linspace(0.0, 1.0, cf, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, cf, dtype=np.float32)
    result[:cf] = result[:cf] * fade_in + before[-cf:] * fade_out
    result[-cf:] = result[-cf:] * fade_out + after[:cf] * fade_in
    return result


def match_duration(modified: np.ndarray, target_samples: int) -> np.ndarray:
    if len(modified) > target_samples:
        return modified[:target_samples]
    if len(modified) < target_samples:
        pad = np.zeros(target_samples - len(modified), dtype=np.float32)
        return np.concatenate([modified, pad])
    return modified


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
    original, src_sr = sf.read(str(wav_path), always_2d=False)
    if original.ndim == 2:
        original = original.mean(axis=1)
    original = resample_audio(original.astype(np.float32), src_sr, SR)

    start_idx = int(start_sec * SR)
    end_idx = min(int(end_sec * SR), len(original))

    before = original[:start_idx]
    original_segment = original[start_idx:end_idx]
    after = original[end_idx:]

    mod_array, mod_sr = _bytes_to_array(modified_wav)
    mod_array = resample_audio(mod_array, mod_sr, SR)

    if force_duration_match:
        mod_array = match_duration(mod_array, target_samples=len(original_segment))

    if normalize_loudness:
        mod_array = rms_normalize(mod_array, reference=original_segment)

    cf_samples = int(SR * crossfade_ms / 1000)
    mod_array = crossfade_edges(mod_array, before=before, after=after, crossfade_samples=cf_samples)

    result = np.concatenate([before, mod_array, after])
    return _array_to_bytes(result, SR)


def slice_segment(wav_path: Path, start_sec: float, end_sec: float) -> tuple[bytes, float]:
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
    end_idx = min(int(end_sec * sr), len(audio))
    segment = audio[start_idx:end_idx]

    segment = resample_audio(segment, src_sr=sr, target_sr=SR)
    return _array_to_bytes(segment, SR), len(segment) / SR


def build_prompt(mode: Literal["style", "melody", "accompaniment"], user_prompt: str) -> str:
    prefixes = {
        "style": "Style transfer — transform the genre/feel of this musical segment while preserving its melody. ",
        "melody": "Melody variation — create a new melodic variation on this segment's theme. ",
        "accompaniment": "Accompaniment generation — generate a harmonic accompaniment for this melody. ",
    }
    return prefixes[mode] + user_prompt


def get_provider(name: Literal["local", "replicate"]) -> AIProvider:
    if name == "local":
        from ..providers.musicgen import MusicGenProvider
        return MusicGenProvider()
    from ..providers.replicate_provider import ReplicateProvider
    return ReplicateProvider()


async def dispatch(
    provider: AIProvider,
    wav_path: Path,
    start_sec: float,
    end_sec: float,
    mode: Literal["style", "melody", "accompaniment"],
    prompt: str,
) -> bytes:
    segment_bytes, duration_sec = slice_segment(wav_path, start_sec, end_sec)
    full_prompt = build_prompt(mode, prompt)
    return await provider.modify(
        segment_audio=segment_bytes,
        segment_duration_sec=duration_sec,
        mode=mode,
        prompt=full_prompt,
    )
