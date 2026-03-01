import numpy as np
import pytest
from pathlib import Path
from backend.services.audio_service import load_audio, get_waveform_data, convert_to_wav


def test_load_audio_returns_numpy_and_sr(sample_wav_path):
    from backend.config import StaticConfig
    audio, sr = load_audio(sample_wav_path)
    assert isinstance(audio, np.ndarray)
    assert sr == StaticConfig.INTERNAL_SAMPLE_RATE
    assert sr == 22050
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
    assert sr == StaticConfig.INTERNAL_SAMPLE_RATE
