import io
import sys
import numpy as np
import soundfile as sf
from unittest.mock import patch, MagicMock
from backend.config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE


def _make_wav(duration_sec: float, sr: int = SR) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def test_replicate_provider_returns_wav_at_internal_rate(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-fake-token")
    mock_mod = MagicMock()
    fake_output_32k = _make_wav(5.0, sr=32000)
    mock_mod.run = MagicMock(return_value="https://fake-replicate-url/output.wav")

    with patch.dict(sys.modules, {"replicate": mock_mod}), \
         patch("backend.providers.replicate_provider._download_bytes", return_value=fake_output_32k):
        from backend.providers.replicate_provider import ReplicateProvider
        provider = ReplicateProvider()
        result = provider.modify(
            segment_audio=_make_wav(5.0),
            segment_duration_sec=5.0,
            mode="style",
            prompt="make it jazzy",
        )

    assert isinstance(result, bytes)
    audio, sr = sf.read(io.BytesIO(result))
    assert sr == SR
    assert len(audio) > 0


def test_replicate_provider_passes_input_audio(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-fake-token")
    mock_mod = MagicMock()
    segment = _make_wav(5.0)
    captured_input = {}

    def fake_run(model, input):
        captured_input.update(input)
        return "https://fake-replicate-url/output.wav"

    mock_mod.run = fake_run

    with patch.dict(sys.modules, {"replicate": mock_mod}), \
         patch("backend.providers.replicate_provider._download_bytes", return_value=_make_wav(5.0, sr=32000)):
        from backend.providers.replicate_provider import ReplicateProvider
        provider = ReplicateProvider()
        provider.modify(
            segment_audio=segment,
            segment_duration_sec=5.0,
            mode="melody",
            prompt="vary the melody",
        )

    assert "input_audio" in captured_input
    assert captured_input["input_audio"].startswith("data:audio/wav;base64,")
