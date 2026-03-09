"""Replicate provider using meta/musicgen with melody conditioning."""
import io
import os
import base64
from typing import Literal
import httpx
import soundfile as sf
import librosa
import numpy as np
from .base import AIProvider
from ..config import StaticConfig

SR = StaticConfig.INTERNAL_SAMPLE_RATE
_MODEL = "meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb"


def _download_bytes(url: str) -> bytes:
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

        b64 = base64.b64encode(segment_audio).decode("ascii")
        input_audio_uri = f"data:audio/wav;base64,{b64}"

        duration = max(2, min(30, int(segment_duration_sec) + 1))

        import replicate

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

        if isinstance(output, str):
            raw_bytes = _download_bytes(output)
        elif hasattr(output, "read"):
            raw_bytes = output.read()
        else:
            raw_bytes = b"".join(list(output))

        audio, src_sr = sf.read(io.BytesIO(raw_bytes), always_2d=False)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        audio = audio.astype(np.float32)
        if src_sr != SR:
            audio = librosa.resample(audio, orig_sr=src_sr, target_sr=SR)

        buf = io.BytesIO()
        sf.write(buf, audio, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
