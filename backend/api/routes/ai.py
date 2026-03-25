"""
AI modification routes.

POST /ai/{track_id}/modify   -- submit async job
GET  /ai/jobs/{job_id}       -- poll job status
GET  /ai/{track_id}/compare  -- original vs AI segment URLs
POST /ai/{track_id}/splice   -- splice AI output into full track
GET  /ai/jobs/{job_id}/result -- stream AI output WAV
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from ...config import StaticConfig
from ...models.schemas import AIJob, Track
from ...services.ai_service import dispatch, splice_segment, get_provider
from ...services.audio_service import load_audio
from ...repositories.file_repo import FileTrackRepository

router = APIRouter(prefix="/ai", tags=["ai"])
_repo = FileTrackRepository()


def _validate_uuid(value: str, label: str = "ID") -> str:
    """Validate that a string is a valid UUID, preventing path traversal."""
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise HTTPException(400, detail=f"Invalid {label}: {value}")


class ModifyRequest(BaseModel):
    mode: Literal["style", "melody", "accompaniment"]
    prompt: str = Field(..., max_length=500)
    start_sec: float = Field(..., ge=0)
    end_sec: float = Field(..., ge=0)
    provider: Literal["local", "replicate"] = "local"

    @model_validator(mode="after")
    def validate_region(self):
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        return self


class SpliceRequest(BaseModel):
    job_id: str
    force_duration_match: bool = False


def _job_path(job_id: str) -> Path:
    StaticConfig.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return StaticConfig.JOBS_DIR / f"{job_id}.json"


def _result_path(job_id: str) -> Path:
    return StaticConfig.JOBS_DIR / f"{job_id}_result.wav"


def _run_job_sync(job: AIJob, wav_path: Path) -> None:
    """Run AI inference synchronously (called from a thread to avoid blocking event loop)."""
    job_path = _job_path(str(job.id))
    try:
        job.status = "running"
        job_path.write_text(job.model_dump_json())

        provider = get_provider(job.provider)
        result_bytes = dispatch(
            provider=provider,
            wav_path=wav_path,
            start_sec=job.start_sec,
            end_sec=job.end_sec,
            mode=job.mode,
            prompt=job.prompt,
        )
        _result_path(str(job.id)).write_bytes(result_bytes)
        job.status = "done"
        job.result_path = str(_result_path(str(job.id)))
    except Exception as exc:
        job.status = "failed"
        job.error_msg = str(exc)
    finally:
        job.updated_at = datetime.now(timezone.utc)
        job_path.write_text(job.model_dump_json())


@router.post("/{track_id}/modify")
async def modify(track_id: str, req: ModifyRequest, background_tasks: BackgroundTasks):
    track_id = _validate_uuid(track_id, "track_id")
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, detail=f"Track not found: {track_id}")

    track = await _repo.get(uuid.UUID(track_id))
    if req.end_sec > track.duration_sec + 0.01:
        raise HTTPException(
            422,
            detail=f"end_sec {req.end_sec}s exceeds track duration {track.duration_sec:.2f}s",
        )

    job = AIJob(
        track_id=uuid.UUID(track_id),
        mode=req.mode,
        prompt=req.prompt,
        provider=req.provider,
        start_sec=req.start_sec,
        end_sec=req.end_sec,
    )
    _job_path(str(job.id)).write_text(job.model_dump_json())
    # _run_job_sync is a regular function; FastAPI runs sync background tasks in a thread pool
    background_tasks.add_task(_run_job_sync, job, wav_path)
    return {"job_id": str(job.id)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job_id = _validate_uuid(job_id, "job_id")
    path = _job_path(job_id)
    if not path.exists():
        raise HTTPException(404, detail=f"Job not found: {job_id}")
    return AIJob.model_validate_json(path.read_text()).model_dump(mode="json", exclude={"result_path"})


@router.get("/jobs/{job_id}/result")
async def get_result(job_id: str):
    job_id = _validate_uuid(job_id, "job_id")
    path = _result_path(job_id)
    if not path.exists():
        raise HTTPException(404, detail="Job result not ready — job may still be running")

    def iter_file():
        with open(path, "rb") as f:
            yield from f

    return StreamingResponse(iter_file(), media_type="audio/wav")


@router.get("/{track_id}/compare")
async def compare(track_id: str, job_id: str):
    track_id = _validate_uuid(track_id, "track_id")
    job_id = _validate_uuid(job_id, "job_id")

    job_path = _job_path(job_id)
    if not job_path.exists():
        raise HTTPException(404, detail=f"Job not found: {job_id}")

    job = AIJob.model_validate_json(job_path.read_text())
    if str(job.track_id) != track_id:
        raise HTTPException(400, detail="Job does not belong to this track")

    result = _result_path(job_id)
    if not result.exists():
        raise HTTPException(404, detail="Job result not ready — job may still be running")
    return {
        "original_url": f"/audio/{track_id}/playback",
        "modified_url": f"/ai/jobs/{job_id}/result",
    }


@router.post("/{track_id}/splice")
async def splice(track_id: str, req: SpliceRequest):
    track_id = _validate_uuid(track_id, "track_id")
    safe_job_id = _validate_uuid(req.job_id, "job_id")

    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, detail=f"Track not found: {track_id}")

    job_path = _job_path(safe_job_id)
    if not job_path.exists():
        raise HTTPException(404, detail=f"Job not found: {safe_job_id}")

    job = AIJob.model_validate_json(job_path.read_text())
    if str(job.track_id) != track_id:
        raise HTTPException(400, detail="Job does not belong to this track")
    if job.status != "done":
        raise HTTPException(409, detail=f"Job not done (status='{job.status}'). Wait for completion.")

    result_path = _result_path(safe_job_id)
    modified_wav = result_path.read_bytes()

    spliced_bytes = splice_segment(
        wav_path=wav_path,
        start_sec=job.start_sec,
        end_sec=job.end_sec,
        modified_wav=modified_wav,
        force_duration_match=req.force_duration_match,
    )

    # Register as a new track
    new_track_id = uuid4()
    new_path = StaticConfig.AUDIO_DIR / f"{new_track_id}.wav"
    new_path.write_bytes(spliced_bytes)

    audio, sr = load_audio(new_path)
    new_track = Track(
        id=new_track_id,
        name=f"AI splice of {track_id[:8]}",
        filename=f"{new_track_id}.wav",
        duration_sec=round(len(audio) / sr, 3),
        sample_rate=sr,
        status="ready",
    )
    await _repo.save(new_track)

    job.spliced_track_id = str(new_track_id)
    job_path.write_text(job.model_dump_json())

    return {"spliced_track_id": str(new_track_id)}
