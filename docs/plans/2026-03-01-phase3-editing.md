# Phase 3: Editing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users select a time region of the track, edit note pitch and timing within that region, play back only the selected region, and re-synthesize to hear changes.

**Architecture:** New `edit_service` handles note mutation logic. New `PUT /midi/{id}/region` bulk-edits all notes in a time range. Frontend adds start/end time inputs for region selection and a "Play Region" button that streams a sliced WAV from the backend.

**Tech Stack:** existing services + `pretty-midi`, new `audio_service.slice_audio`, new region route.

**Prerequisite:** Phase 2 complete and passing.

---

## Task 1: edit_service

**Files:**
- Create: `backend/services/edit_service.py`
- Create: `tests/backend/test_edit_service.py`

**Step 1: Write failing tests**

```python
# tests/backend/test_edit_service.py
from uuid import uuid4
from backend.models.schemas import Note
from backend.services.edit_service import (
    shift_pitch,
    shift_timing,
    notes_in_region,
    apply_pitch_shift_to_region,
)


def _note(pitch=60, start=0.0, end=0.5) -> Note:
    return Note(track_id=uuid4(), pitch_midi=pitch, start_sec=start, end_sec=end, velocity=80)


def test_shift_pitch_clamps_to_valid_midi():
    note = _note(pitch=126)
    result = shift_pitch(note, semitones=5)
    assert result.pitch_midi == 127  # clamped


def test_shift_pitch_negative():
    note = _note(pitch=60)
    result = shift_pitch(note, semitones=-3)
    assert result.pitch_midi == 57


def test_shift_timing_moves_note():
    note = _note(start=1.0, end=1.5)
    result = shift_timing(note, delta_sec=0.5)
    assert abs(result.start_sec - 1.5) < 0.001
    assert abs(result.end_sec - 2.0) < 0.001


def test_notes_in_region_filters_correctly():
    notes = [_note(start=0.0, end=0.5), _note(start=1.0, end=1.5), _note(start=2.0, end=2.5)]
    result = notes_in_region(notes, start_sec=0.8, end_sec=1.8)
    assert len(result) == 1
    assert result[0].start_sec == 1.0


def test_apply_pitch_shift_to_region():
    notes = [_note(pitch=60, start=0.0, end=0.5), _note(pitch=62, start=1.0, end=1.5)]
    result = apply_pitch_shift_to_region(notes, start_sec=0.8, end_sec=1.8, semitones=2)
    pitches = {n.start_sec: n.pitch_midi for n in result}
    assert pitches[0.0] == 60   # outside region, unchanged
    assert pitches[1.0] == 64   # inside region, shifted +2
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_edit_service.py -v
```
Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# backend/services/edit_service.py
from ..models.schemas import Note


def shift_pitch(note: Note, semitones: int) -> Note:
    new_pitch = max(0, min(127, note.pitch_midi + semitones))
    return note.model_copy(update={"pitch_midi": new_pitch})


def shift_timing(note: Note, delta_sec: float) -> Note:
    new_start = max(0.0, note.start_sec + delta_sec)
    new_end = max(new_start + 0.01, note.end_sec + delta_sec)
    return note.model_copy(update={"start_sec": new_start, "end_sec": new_end})


def notes_in_region(notes: list[Note], start_sec: float, end_sec: float) -> list[Note]:
    return [n for n in notes if n.start_sec >= start_sec and n.end_sec <= end_sec]


def apply_pitch_shift_to_region(
    notes: list[Note], start_sec: float, end_sec: float, semitones: int
) -> list[Note]:
    return [
        shift_pitch(n, semitones) if start_sec <= n.start_sec and n.end_sec <= end_sec else n
        for n in notes
    ]


def apply_timing_shift_to_region(
    notes: list[Note], start_sec: float, end_sec: float, delta_sec: float
) -> list[Note]:
    return [
        shift_timing(n, delta_sec) if start_sec <= n.start_sec and n.end_sec <= end_sec else n
        for n in notes
    ]
```

**Step 4: Run to verify passes**

```bash
pytest tests/backend/test_edit_service.py -v
```
Expected: 5 passed

**Step 5: Commit**

```bash
git add backend/services/edit_service.py tests/backend/test_edit_service.py
git commit -m "feat: edit_service — pitch/timing shift and region operations"
```

---

## Task 2: Audio Slicing (Region Playback)

**Files:**
- Modify: `backend/services/audio_service.py`
- Modify: `tests/backend/test_audio_service.py`

**Step 1: Add failing test**

```python
# append to tests/backend/test_audio_service.py
from backend.services.audio_service import slice_audio

def test_slice_audio_correct_duration(sample_wav_path, tmp_path):
    out = tmp_path / "slice.wav"
    slice_audio(sample_wav_path, out, start_sec=0.5, end_sec=1.5)
    audio, sr = load_audio(out)
    duration = len(audio) / sr
    assert abs(duration - 1.0) < 0.05  # within 50ms
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_audio_service.py::test_slice_audio_correct_duration -v
```

**Step 3: Implement**

```python
# append to backend/services/audio_service.py

def slice_audio(src_path: Path, dest_path: Path, start_sec: float, end_sec: float) -> None:
    """Extract a time slice of an audio file."""
    audio, sr = load_audio(src_path)
    start_sample = int(start_sec * sr)
    end_sample = int(end_sec * sr)
    sliced = audio[start_sample:end_sample]
    save_audio(sliced, sr, dest_path)
```

**Step 4: Run to verify passes**

```bash
pytest tests/backend/test_audio_service.py -v
```

**Step 5: Commit**

```bash
git add backend/services/audio_service.py tests/backend/test_audio_service.py
git commit -m "feat: audio_service.slice_audio for region playback"
```

---

## Task 3: Region Routes

**Files:**
- Modify: `backend/api/routes/midi.py`
- Modify: `backend/api/routes/audio.py`
- Modify: `tests/backend/test_routes.py`

**Step 1: Add failing tests**

```python
# append to tests/backend/test_routes.py

@pytest.mark.anyio
async def test_region_pitch_shift(client, wav_bytes):
    upload = await client.post("/audio/upload", files={"file": ("t.wav", wav_bytes, "audio/wav")})
    tid = upload.json()["track_id"]
    await client.post(f"/midi/{tid}/extract")

    resp = await client.put(f"/midi/{tid}/region", json={
        "start_sec": 0.0, "end_sec": 10.0, "pitch_shift": 2
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "notes" in data


@pytest.mark.anyio
async def test_region_playback_streams_audio(client, wav_bytes):
    upload = await client.post("/audio/upload", files={"file": ("t.wav", wav_bytes, "audio/wav")})
    tid = upload.json()["track_id"]
    resp = await client.get(f"/audio/{tid}/region?start_sec=0.0&end_sec=1.0")
    assert resp.status_code == 200
    assert "audio" in resp.headers["content-type"]
```

**Step 2: Run to verify fails**

```bash
pytest tests/backend/test_routes.py::test_region_pitch_shift -v
```

**Step 3: Add region route to midi.py**

```python
# append to backend/api/routes/midi.py
from ...services.edit_service import apply_pitch_shift_to_region, apply_timing_shift_to_region
from pydantic import BaseModel as _BaseModel


class RegionEditPayload(_BaseModel):
    start_sec: float
    end_sec: float
    pitch_shift: int = 0
    timing_shift: float = 0.0


@router.put("/{track_id}/region")
async def edit_region(track_id: str, payload: RegionEditPayload):
    path = _notes_path(track_id)
    if not path.exists():
        raise HTTPException(404, "MIDI not extracted yet")
    notes = [Note.model_validate(n) for n in json.loads(path.read_text())]
    if payload.pitch_shift != 0:
        notes = apply_pitch_shift_to_region(notes, payload.start_sec, payload.end_sec, payload.pitch_shift)
    if payload.timing_shift != 0.0:
        notes = apply_timing_shift_to_region(notes, payload.start_sec, payload.end_sec, payload.timing_shift)
    notes_data = [n.model_dump(mode="json") for n in notes]
    path.write_text(json.dumps(notes_data))
    return {"notes": notes_data}
```

**Step 4: Add region playback to audio.py**

```python
# append to backend/api/routes/audio.py
from ...services.audio_service import slice_audio
import tempfile, os

@router.get("/{track_id}/region")
async def get_region(track_id: str, start_sec: float = 0.0, end_sec: float = 10.0):
    wav_path = StaticConfig.AUDIO_DIR / f"{track_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Track not found")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    slice_audio(wav_path, Path(tmp.name), start_sec, end_sec)
    def iter_and_clean():
        with open(tmp.name, "rb") as f:
            yield from f
        os.unlink(tmp.name)
    return StreamingResponse(iter_and_clean(), media_type="audio/wav")
```

**Step 5: Run to verify passes**

```bash
pytest tests/backend/test_routes.py -v
```

**Step 6: Commit**

```bash
git add backend/api/routes/midi.py backend/api/routes/audio.py tests/backend/test_routes.py
git commit -m "feat: region edit (pitch/timing shift) and region playback routes"
```

---

## Task 4: Frontend Editor Enhancements

**Files:**
- Modify: `frontend/api_client.py`
- Modify: `frontend/pages/editor.py`

**Step 1: Add region methods to api_client.py**

```python
# append to frontend/api_client.py

def edit_region(track_id: str, start_sec: float, end_sec: float,
                pitch_shift: int = 0, timing_shift: float = 0.0) -> dict:
    resp = _client.put(f"/midi/{track_id}/region", json={
        "start_sec": start_sec, "end_sec": end_sec,
        "pitch_shift": pitch_shift, "timing_shift": timing_shift,
    })
    resp.raise_for_status()
    return resp.json()


def get_region_playback_url(track_id: str, start_sec: float, end_sec: float) -> str:
    return f"{BACKEND_URL}/audio/{track_id}/region?start_sec={start_sec}&end_sec={end_sec}"
```

**Step 2: Add region controls to editor.py**

Replace the editor page's note section with:

```python
# frontend/pages/editor.py — add Region Controls section before note list

    st.subheader("Region Controls")
    rcol1, rcol2 = st.columns(2)
    with rcol1:
        r_start = st.number_input("Region start (s)", 0.0, value=0.0, step=0.1, key="r_start")
    with rcol2:
        r_end = st.number_input("Region end (s)", 0.0, value=5.0, step=0.1, key="r_end")

    st.audio(api_client.get_region_playback_url(track_id, r_start, r_end))

    ecol1, ecol2, ecol3 = st.columns(3)
    with ecol1:
        pitch_shift = st.number_input("Pitch shift (semitones)", -24, 24, 0, key="ps")
    with ecol2:
        timing_shift = st.number_input("Timing shift (s)", -5.0, 5.0, 0.0, step=0.1, key="ts")
    with ecol3:
        st.write("")  # spacer
        if st.button("Apply to Region"):
            result = api_client.edit_region(track_id, r_start, r_end, pitch_shift, timing_shift)
            st.session_state["notes"] = result["notes"]
            st.success(f"Applied. Re-synthesize to hear changes.")
```

**Step 3: Manual smoke test**

```bash
scripts/ctl restart
```
Upload a track → Extract MIDI → set Region 0–2s → play region → apply +5 semitones → Synthesize → play — pitch of first 2s should be noticeably higher.

**Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: region select, pitch/timing shift UI, and region playback"
```

---

## Task 5: Extend Integration Test

**Files:**
- Modify: `scripts/run_integration_test.sh`

```bash
# append before final echo in run_integration_test.sh

echo "[6/6] Region edit + synthesize..."
curl -sf -X PUT "$BACKEND/midi/$TRACK_ID/region" \
  -H "Content-Type: application/json" \
  -d '{"start_sec":0.0,"end_sec":5.0,"pitch_shift":2}' > /dev/null
curl -sf -X POST "$BACKEND/midi/$TRACK_ID/synthesize" > /dev/null
echo "      PASS"
```

```bash
scripts/ctl test integration
```
Expected: 6/6 PASS

```bash
git add scripts/run_integration_test.sh
git commit -m "test: extend integration test to cover region editing"
```

---

## Phase 3 Complete Checklist

- [ ] `ctl test unit` — all pass
- [ ] `ctl test integration` — 6/6 pass
- [ ] Region select inputs visible in Editor
- [ ] Region playback streams correct slice of audio
- [ ] Pitch shift applied to region → synthesize → audible pitch difference
- [ ] Individual note pitch/timing edit still works
