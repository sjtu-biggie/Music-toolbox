"""MusicGen-Melody provider for local GPU inference."""
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
    from transformers import AutoProcessor, MusicgenMelodyForConditionalGeneration
    processor = AutoProcessor.from_pretrained("facebook/musicgen-melody")
    model = MusicgenMelodyForConditionalGeneration.from_pretrained("facebook/musicgen-melody")
    try:
        model = model.to("cuda")
    except Exception:
        pass
    return processor, model


class MusicGenProvider(AIProvider):
    async def modify(
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

        generated = audio_values[0].cpu().numpy()
        if generated.ndim == 2:
            generated = generated.mean(axis=0)
        generated = generated.astype(np.float32)

        if model_sr != SR:
            generated = librosa.resample(generated, orig_sr=model_sr, target_sr=SR)

        buf = io.BytesIO()
        sf.write(buf, generated, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
