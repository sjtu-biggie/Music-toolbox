import pytest
from uuid import uuid4
from backend.models.schemas import Track
from backend.repositories.file_repo import FileTrackRepository
from backend.config import StaticConfig


@pytest.fixture(autouse=True)
def setup_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(StaticConfig, "TRACKS_DIR", tmp_path / "tracks")
    monkeypatch.setattr(StaticConfig, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(StaticConfig, "MIDI_DIR", tmp_path / "midi")
    monkeypatch.setattr(StaticConfig, "JOBS_DIR", tmp_path / "jobs")
    StaticConfig.ensure_dirs()


@pytest.mark.asyncio
async def test_save_and_get_track():
    repo = FileTrackRepository()
    track = Track(filename="song.mp3", duration_sec=3.0, sample_rate=22050, status="ready")
    await repo.save(track)
    loaded = await repo.get(track.id)
    assert loaded.id == track.id
    assert loaded.filename == "song.mp3"


@pytest.mark.asyncio
async def test_get_missing_track_raises():
    repo = FileTrackRepository()
    with pytest.raises(KeyError):
        await repo.get(uuid4())
