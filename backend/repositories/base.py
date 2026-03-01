from abc import ABC, abstractmethod
from uuid import UUID
from ..models.schemas import Track


class TrackRepository(ABC):
    @abstractmethod
    async def save(self, track: Track) -> Track: ...

    @abstractmethod
    async def get(self, track_id: UUID) -> Track: ...
