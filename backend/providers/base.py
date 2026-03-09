from abc import ABC, abstractmethod
from typing import Literal


class AIProvider(ABC):
    @abstractmethod
    async def modify(
        self,
        segment_audio: bytes,
        segment_duration_sec: float,
        mode: Literal["style", "melody", "accompaniment"],
        prompt: str,
    ) -> bytes:
        """Return modified segment audio as WAV bytes at INTERNAL_SAMPLE_RATE."""
        ...
