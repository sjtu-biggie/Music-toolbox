import io
import numpy as np
import soundfile as sf
from unittest.mock import patch, MagicMock
from backend.config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE
MODEL_SR = 32000


def _make_wav(duration_sec: float, sr: int = SR) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def test_musicgen_provider_returns_wav_at_internal_rate():
    from backend.providers.musicgen import MusicGenProvider

    fake_audio_32k = np.zeros(int(MODEL_SR * 5), dtype=np.float32)
    fake_output = MagicMock()
    fake_single = MagicMock()
    fake_single.cpu.return_value.numpy.return_value = fake_audio_32k[np.newaxis, :]
    fake_output.__getitem__ = MagicMock(return_value=fake_single)
    fake_tensor = fake_output

    mock_torch = MagicMock()
    mock_torch.Tensor = type("FakeTensor", (), {})
    mock_torch.no_grad.return_value.__enter__ = MagicMock()
    mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=False)

    with patch("backend.providers.musicgen._load_model") as mock_load, \
         patch.dict("sys.modules", {"torch": mock_torch}):
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_processor.return_value = {"input_ids": MagicMock(), "input_features": MagicMock()}
        mock_model.generate.return_value = fake_tensor
        mock_model.config.audio_encoder.sampling_rate = MODEL_SR
        mock_load.return_value = (mock_processor, mock_model)

        provider = MusicGenProvider()
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


def test_musicgen_provider_satisfies_abc():
    from backend.providers.musicgen import MusicGenProvider
    from backend.providers.base import AIProvider
    assert issubclass(MusicGenProvider, AIProvider)
