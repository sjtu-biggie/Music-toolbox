import shutil
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from ...config import StaticConfig
from ...models.schemas import Track
from ...repositories.file_repo import FileTrackRepository
from ...services.audio_service import convert_to_wav, get_waveform_data, load_audio, slice_audio

router = APIRouter(prefix="/audio", tags=["audio"])
_repo = FileTrackRepository()
_ALLOWED = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...), name: str = Form(...)):
    if not name.strip():
        raise HTTPException(400, "Track name is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(400, f"Unsupported format '{suffix}'. Allowed: {_ALLOWED}")
    StaticConfig.ensure_dirs()
    track_id = uuid4()
    raw_path = StaticConfig.TRACKS_DIR / f"{track_id}{suffix}"
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    convert_to_wav(raw_path, wav_path)
    audio, sr = load_audio(wav_path)
    track = Track(
        id=track_id,
        name=name.strip(),
        filename=file.filename,
        duration_sec=round(len(audio) / sr, 3),
        sample_rate=sr,
        status="ready",
    )
    await _repo.save(track)
    return {
        "track_id": str(track_id),
        "name": track.name,
        "duration_sec": track.duration_sec,
        "sample_rate": sr,
    }


@router.post("/record")
async def record_audio(file: UploadFile = File(...), name: str = Form(...)):
    """Accept browser mic recording blob. Identical pipeline to /upload."""
    if not name.strip():
        raise HTTPException(400, "Track name is required")
    StaticConfig.ensure_dirs()
    track_id = uuid4()
    # Chromium sends audio/webm, Firefox sends audio/ogg — librosa handles both via ffmpeg
    ct = (file.content_type or "").lower()
    if "webm" in ct:
        suffix = ".webm"
    elif "ogg" in ct:
        suffix = ".ogg"
    else:
        suffix = ".wav"
    raw_path = StaticConfig.TRACKS_DIR / f"{track_id}{suffix}"
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    convert_to_wav(raw_path, wav_path)
    audio, sr = load_audio(wav_path)
    track = Track(
        id=track_id,
        name=name.strip(),
        filename=f"recording{suffix}",
        duration_sec=round(len(audio) / sr, 3),
        sample_rate=sr,
        status="ready",
    )
    await _repo.save(track)
    return {
        "track_id": str(track_id),
        "name": track.name,
        "duration_sec": track.duration_sec,
        "sample_rate": sr,
    }


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


@router.get("/{track_id}/region")
async def get_region(track_id: str, start_sec: float = 0.0, end_sec: float = 10.0):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    import tempfile
    import os
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    slice_audio(wav_path, Path(tmp.name), start_sec, end_sec)

    def iter_and_clean():
        with open(tmp.name, "rb") as f:
            yield from f
        os.unlink(tmp.name)

    return StreamingResponse(iter_and_clean(), media_type="audio/wav")
