import io
import sys
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


@pytest.fixture(autouse=True)
def mock_replicate_module(monkeypatch):
    """Ensure 'replicate' is importable even if not installed, and set token."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-fake-token")
    mock_mod = MagicMock()
    with patch.dict(sys.modules, {"replicate": mock_mod}):
        yield mock_mod


@pytest.mark.asyncio
async def test_replicate_provider_returns_wav_at_internal_rate(mock_replicate_module):
    from backend.providers.replicate_provider import ReplicateProvider

    fake_output_32k = _make_wav(5.0, sr=32000)
    mock_replicate_module.run = MagicMock(return_value="https://fake-replicate-url/output.wav")

    with patch("backend.providers.replicate_provider._download_bytes", return_value=fake_output_32k):
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
async def test_replicate_provider_passes_input_audio(mock_replicate_module):
    from backend.providers.replicate_provider import ReplicateProvider

    segment = _make_wav(5.0)
    captured_input = {}

    def fake_run(model, input):
        captured_input.update(input)
        return "https://fake-replicate-url/output.wav"

    mock_replicate_module.run = fake_run

    with patch("backend.providers.replicate_provider._download_bytes", return_value=_make_wav(5.0, sr=32000)):
        provider = ReplicateProvider()
        await provider.modify(
            segment_audio=segment,
            segment_duration_sec=5.0,
            mode="melody",
            prompt="vary the melody",
        )

    assert "input_audio" in captured_input
    assert captured_input["input_audio"].startswith("data:audio/wav;base64,")
