from pathlib import Path
import numpy as np
import librosa
import soundfile as sf
from ..config import StaticConfig


def load_audio(file_path: Path) -> tuple[np.ndarray, int]:
    audio, sr = librosa.load(str(file_path), sr=StaticConfig.INTERNAL_SAMPLE_RATE, mono=True)
    return audio.astype(np.float32), StaticConfig.INTERNAL_SAMPLE_RATE


def save_audio(audio: np.ndarray, sr: int, dest_path: Path) -> None:
    sf.write(str(dest_path), audio, sr, subtype="PCM_16")


def get_waveform_data(
    audio: np.ndarray, sr: int, max_points: int = StaticConfig.WAVEFORM_MAX_POINTS
) -> dict:
    duration = len(audio) / sr
    step = max(1, len(audio) // max_points)
    times = (np.arange(0, len(audio), step)[:max_points] / sr).tolist()
    amplitudes = audio[::step][:max_points].tolist()
    return {"times": times, "amplitudes": amplitudes, "duration_sec": duration}


def convert_to_wav(src_path: Path, dest_path: Path) -> None:
    audio, sr = load_audio(src_path)
    save_audio(audio, sr, dest_path)


def slice_audio(src_path: Path, dest_path: Path, start_sec: float, end_sec: float) -> None:
    """Extract a time slice of an audio file."""
    audio, sr = load_audio(src_path)
    start_sample = int(start_sec * sr)
    end_sample = int(end_sec * sr)
    sliced = audio[start_sample:end_sample]
    save_audio(sliced, sr, dest_path)
