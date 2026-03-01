from uuid import UUID
from datetime import datetime
from backend.models.schemas import Track, Note, AIJob


def test_track_has_uuid_and_timestamps():
    track = Track(filename="song.mp3", duration_sec=3.0, sample_rate=22050, status="ready")
    assert isinstance(track.id, UUID)
    assert isinstance(track.created_at, datetime)
    assert isinstance(track.updated_at, datetime)


def test_note_links_to_track():
    from uuid import uuid4
    track_id = uuid4()
    note = Note(track_id=track_id, pitch_midi=60, start_sec=0.0, end_sec=0.5, velocity=80)
    assert note.track_id == track_id
    assert isinstance(note.id, UUID)


def test_aijob_status_default_pending():
    from uuid import uuid4
    job = AIJob(
        track_id=uuid4(),
        mode="style",
        prompt="make it jazzy",
        provider="local",
        start_sec=1.0,
        end_sec=3.0,
    )
    assert job.status == "pending"
    assert job.result_path is None
