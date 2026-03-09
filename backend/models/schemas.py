from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Track(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    filename: str
    duration_sec: float
    sample_rate: int
    status: Literal["uploading", "ready", "processing"]
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Note(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    pitch_midi: int   # 0-127
    start_sec: float
    end_sec: float
    velocity: int     # 0-127


class NoteUpdate(BaseModel):
    pitch_midi: int | None = Field(default=None, ge=0, le=127)
    start_sec: float | None = Field(default=None, ge=0)
    end_sec: float | None = Field(default=None, ge=0)
    velocity: int | None = Field(default=None, ge=0, le=127)


class AIJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    track_id: UUID
    mode: Literal["style", "melody", "accompaniment"]
    prompt: str
    provider: Literal["local", "replicate"]
    start_sec: float
    end_sec: float
    status: Literal["pending", "running", "done", "failed"] = "pending"
    result_path: str | None = None
    spliced_track_id: str | None = None
    error_msg: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
