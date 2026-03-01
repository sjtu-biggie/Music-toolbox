from uuid import UUID
from pathlib import Path
from .base import TrackRepository
from ..models.schemas import Track
from ..config import StaticConfig


class FileTrackRepository(TrackRepository):
    def _path(self, track_id: UUID) -> Path:
        return StaticConfig.TRACKS_DIR / f"{track_id}.json"

    async def save(self, track: Track) -> Track:
        StaticConfig.TRACKS_DIR.mkdir(parents=True, exist_ok=True)
        self._path(track.id).write_text(track.model_dump_json())
        return track

    async def get(self, track_id: UUID) -> Track:
        path = self._path(track_id)
        if not path.exists():
            raise KeyError(f"Track {track_id} not found")
        return Track.model_validate_json(path.read_text())
