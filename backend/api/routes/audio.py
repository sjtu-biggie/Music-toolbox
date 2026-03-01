import shutil
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from ...config import StaticConfig
from ...models.schemas import Track
from ...repositories.file_repo import FileTrackRepository
from ...services.audio_service import convert_to_wav, get_waveform_data, load_audio

router = APIRouter(prefix="/audio", tags=["audio"])
_repo = FileTrackRepository()
_ALLOWED = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(400, f"Unsupported format '{suffix}'. Allowed: {_ALLOWED}")
    StaticConfig.ensure_dirs()
    from uuid import uuid4
    track_id = uuid4()
    raw_path = StaticConfig.TRACKS_DIR / f"{track_id}{suffix}"
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    convert_to_wav(raw_path, wav_path)
    audio, sr = load_audio(wav_path)
    track = Track(
        id=track_id,
        filename=file.filename,
        duration_sec=round(len(audio) / sr, 3),
        sample_rate=sr,
        status="ready",
    )
    await _repo.save(track)
    return {"track_id": str(track_id), "duration_sec": track.duration_sec, "sample_rate": sr}


@router.get("/{track_id}/waveform")
async def get_waveform(track_id: str):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    audio, sr = load_audio(wav_path)
    return get_waveform_data(audio, sr)


@router.get("/{track_id}/playback")
async def get_playback(track_id: str):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    return StreamingResponse(open(wav_path, "rb"), media_type="audio/wav")
