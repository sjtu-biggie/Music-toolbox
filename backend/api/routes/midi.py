import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ...config import StaticConfig
from ...models.schemas import Note
from ...repositories.file_repo import FileTrackRepository
from ...services.midi_service import extract_midi, notes_to_midi, synthesize_midi

router = APIRouter(prefix="/midi", tags=["midi"])
_repo = FileTrackRepository()


@router.get("/instruments/list")
async def list_instruments():
    return {"instruments": list(StaticConfig.INSTRUMENTS.keys()), "default": StaticConfig.DEFAULT_INSTRUMENT}


def _notes_path(track_id: str) -> Path:
    return StaticConfig.MIDI_DIR / f"{track_id}_notes.json"


def _midi_path(track_id: str) -> Path:
    return StaticConfig.MIDI_DIR / f"{track_id}.mid"


def _synth_path(track_id: str) -> Path:
    return StaticConfig.AUDIO_DIR / f"{track_id}_synth.wav"


@router.post("/{track_id}/extract")
async def extract(track_id: str):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    from uuid import UUID
    midi_path = _midi_path(track_id)
    StaticConfig.MIDI_DIR.mkdir(parents=True, exist_ok=True)
    notes = extract_midi(wav_path, midi_path, track_id=UUID(track_id))
    notes_data = [n.model_dump(mode="json") for n in notes]
    _notes_path(track_id).write_text(json.dumps(notes_data))
    return {"notes": notes_data}


@router.get("/{track_id}")
async def get_notes(track_id: str):
    path = _notes_path(track_id)
    if not path.exists():
        raise HTTPException(404, "MIDI not extracted yet")
    return {"notes": json.loads(path.read_text())}


@router.put("/{track_id}/notes/{note_id}")
async def update_note(track_id: str, note_id: str, payload: dict):
    path = _notes_path(track_id)
    if not path.exists():
        raise HTTPException(404, "MIDI not extracted yet")
    notes_data = json.loads(path.read_text())
    for note in notes_data:
        if note["id"] == note_id:
            note.update({k: v for k, v in payload.items() if k in ("pitch_midi", "start_sec", "end_sec", "velocity")})
            path.write_text(json.dumps(notes_data))
            return note
    raise HTTPException(404, f"Note {note_id} not found")


@router.post("/{track_id}/synthesize")
async def synthesize(track_id: str, instrument: str = StaticConfig.DEFAULT_INSTRUMENT):
    path = _notes_path(track_id)
    if not path.exists():
        raise HTTPException(404, "MIDI not extracted yet")
    if instrument not in StaticConfig.INSTRUMENTS:
        raise HTTPException(400, f"Unknown instrument '{instrument}'. Available: {list(StaticConfig.INSTRUMENTS.keys())}")
    program = StaticConfig.INSTRUMENTS[instrument]
    notes = [Note.model_validate(n) for n in json.loads(path.read_text())]
    midi_path = _midi_path(track_id)
    notes_to_midi(notes, midi_path, program=program)
    synth_path = _synth_path(track_id)
    synthesize_midi(midi_path, synth_path)
    return {"playback_url": f"/audio/{track_id}/synth", "instrument": instrument}


@router.get("/{track_id}/playback")
async def midi_playback(track_id: str):
    synth_path = _synth_path(track_id)
    if not synth_path.exists():
        raise HTTPException(404, "Not synthesized yet — call POST /midi/{id}/synthesize first")
    return StreamingResponse(open(synth_path, "rb"), media_type="audio/wav")
