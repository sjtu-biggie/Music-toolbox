"""MusicGen-Melody provider for local GPU inference."""
import io
import logging
import threading
from typing import Literal
import numpy as np
import soundfile as sf
import librosa
from .base import AIProvider
from ..config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE
logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_cached_model: tuple | None = None


def _load_model():
    """Load processor and model once, thread-safe."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    with _model_lock:
        if _cached_model is not None:
            return _cached_model
        from transformers import AutoProcessor, MusicgenMelodyForConditionalGeneration
        processor = AutoProcessor.from_pretrained("facebook/musicgen-melody")
        model = MusicgenMelodyForConditionalGeneration.from_pretrained("facebook/musicgen-melody")
        try:
            model = model.to("cuda")
        except Exception as exc:
            logger.warning("Failed to move model to CUDA, falling back to CPU: %s", exc)
        _cached_model = (processor, model)
        return _cached_model


class MusicGenProvider(AIProvider):
    def modify(
        self,
        segment_audio: bytes,
        segment_duration_sec: float,
        mode: Literal["style", "melody", "accompaniment"],
        prompt: str,
    ) -> bytes:
        processor, model = _load_model()
        model_sr: int = model.config.audio_encoder.sampling_rate

        seg_array, seg_sr = sf.read(io.BytesIO(segment_audio), always_2d=False)
        if seg_array.ndim == 2:
            seg_array = seg_array.mean(axis=1)
        if seg_sr != model_sr:
            seg_array = librosa.resample(
                seg_array.astype(np.float32), orig_sr=seg_sr, target_sr=model_sr
            )
        seg_array = seg_array.astype(np.float32)

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

        # Shape: (batch, channels, samples) -> take first batch item
        generated = audio_values[0].cpu().numpy()
        if generated.ndim == 2:
            generated = generated.mean(axis=0)
        generated = generated.astype(np.float32)

        if model_sr != SR:
            generated = librosa.resample(generated, orig_sr=model_sr, target_sr=SR)

        buf = io.BytesIO()
        sf.write(buf, generated, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
