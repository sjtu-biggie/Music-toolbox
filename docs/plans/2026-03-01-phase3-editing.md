# Phase 3: Editing (Piano Roll) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users visually edit notes on a canvas-based piano roll (drag to move pitch/timing, resize duration), select regions by click-dragging empty space (synced with WaveSurfer.js waveform), play back selected regions, and apply bulk pitch/timing shifts. Re-synthesize on edit.

**Architecture:** New `edit_service` handles note mutation logic. New `PUT /midi/{id}/region` bulk-edits all notes in a time range. Frontend adds a canvas-based piano roll below the WaveSurfer.js waveform. Region selection is shared between waveform and piano roll. Both call existing backend routes.

**Tech Stack:** existing backend services + `pretty-midi`, new `audio_service.slice_audio`, new region route. Frontend: HTML5 Canvas piano roll, WaveSurfer.js regions plugin.

**Prerequisite:** Phase 2.5 complete and passing.

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

## Task 4: Piano Roll Canvas Component

**Files:**
- Create: `frontend/src/lib/canvas-utils.ts`
- Create: `frontend/src/components/piano-roll.ts`
- Modify: `frontend/src/api.ts` (add region edit method)

This is the core UI component. It renders notes on a canvas and handles mouse interactions for selection, dragging, and region creation.

**Step 1: Add region edit to api.ts**

```typescript
// append to frontend/src/api.ts

export async function editRegion(
  trackId: string,
  startSec: number,
  endSec: number,
  pitchShift = 0,
  timingShift = 0.0
): Promise<{ notes: Note[] }> {
  return request(`/midi/${trackId}/region`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_sec: startSec,
      end_sec: endSec,
      pitch_shift: pitchShift,
      timing_shift: timingShift,
    }),
  });
}
```

**Step 2: Create canvas utilities**

```typescript
// frontend/src/lib/canvas-utils.ts

/** Convert MIDI pitch number to note name (e.g. 60 → "C4") */
export function midiToNoteName(midi: number): string {
  const names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const octave = Math.floor(midi / 12) - 1;
  return `${names[midi % 12]}${octave}`;
}

/** Returns true if the MIDI pitch is a black key */
export function isBlackKey(midi: number): boolean {
  return [1, 3, 6, 8, 10].includes(midi % 12);
}

export interface Viewport {
  /** Leftmost visible time in seconds */
  scrollX: number;
  /** Lowest visible MIDI pitch */
  scrollY: number;
  /** Seconds per pixel (zoom level) */
  secPerPx: number;
  /** Number of visible semitone rows */
  visiblePitchRange: number;
}

export function defaultViewport(): Viewport {
  return {
    scrollX: 0,
    scrollY: 48,       // C3 — reasonable default for vocals
    secPerPx: 0.01,    // 100px per second
    visiblePitchRange: 36, // 3 octaves visible
  };
}

export interface PianoRollTheme {
  background: string;
  gridLine: string;
  gridLineBeat: string;
  whiteRow: string;
  blackRow: string;
  noteColor: string;
  noteSelectedColor: string;
  noteBorder: string;
  regionColor: string;
  textColor: string;
  keyLabelBg: string;
}

export const darkTheme: PianoRollTheme = {
  background: "#1a1a2e",
  gridLine: "#2a2a4a",
  gridLineBeat: "#3a3a5a",
  whiteRow: "#1e1e36",
  blackRow: "#16162e",
  noteColor: "#e94560",
  noteSelectedColor: "#ff6b81",
  noteBorder: "#ff8fa3",
  regionColor: "rgba(233, 69, 96, 0.15)",
  textColor: "#a0a0a0",
  keyLabelBg: "#0f0f24",
};
```

**Step 3: Create piano roll component**

The piano roll is a single `<canvas>` element with mouse event handlers. Key design:

- **Rendering:** On each frame, clear canvas and draw: row backgrounds (alternating for black/white keys), grid lines, key labels on the left, note rectangles, region highlight, selection handles.
- **Hit testing:** On mouse down, check if cursor is over a note body (→ start drag), note left edge (→ resize start), note right edge (→ resize end), or empty area (→ start region selection).
- **Dragging:** On mouse move during drag, compute delta in pitch (y) and time (x), snap to grid, update note position visually. On mouse up, fire API call to persist the change.
- **Region selection:** On mouse down on empty area → start. On mouse move → expand region rectangle. On mouse up → finalize region. Emit a `regionchange` custom event so the waveform component can sync.

```typescript
// frontend/src/components/piano-roll.ts
import { defaultViewport, darkTheme, midiToNoteName, isBlackKey } from "../lib/canvas-utils";
import type { Viewport, PianoRollTheme } from "../lib/canvas-utils";
import { updateNote, editRegion } from "../api";
import type { Note } from "../api";

const KEY_LABEL_WIDTH = 48; // pixels reserved for pitch labels on left
const NOTE_HEIGHT_PX = 16;  // height of one semitone row
const MIN_NOTE_WIDTH_PX = 4;

interface DragState {
  type: "move" | "resize-left" | "resize-right";
  noteId: string;
  startMouseX: number;
  startMouseY: number;
  origPitch: number;
  origStartSec: number;
  origEndSec: number;
}

interface RegionDragState {
  startX: number;
  currentX: number;
}

export interface PianoRollOptions {
  trackId: string;
  notes: Note[];
  durationSec: number;
  /** Called when notes change (after API update) */
  onNotesChange: (notes: Note[]) => void;
  /** Called when region selection changes */
  onRegionChange: (region: { startSec: number; endSec: number } | null) => void;
  /** Called to request a re-synthesize */
  onRequestSynthesize: () => void;
}

export class PianoRoll {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private viewport: Viewport;
  private theme: PianoRollTheme = darkTheme;
  private notes: Note[];
  private selectedNoteIds: Set<string> = new Set();
  private region: { startSec: number; endSec: number } | null = null;
  private drag: DragState | null = null;
  private regionDrag: RegionDragState | null = null;
  private trackId: string;
  private durationSec: number;
  private onNotesChange: (notes: Note[]) => void;
  private onRegionChange: (region: { startSec: number; endSec: number } | null) => void;
  private onRequestSynthesize: () => void;

  constructor(container: HTMLElement, options: PianoRollOptions) {
    this.trackId = options.trackId;
    this.notes = options.notes;
    this.durationSec = options.durationSec;
    this.onNotesChange = options.onNotesChange;
    this.onRegionChange = options.onRegionChange;
    this.onRequestSynthesize = options.onRequestSynthesize;
    this.viewport = defaultViewport();

    this.canvas = document.createElement("canvas");
    this.canvas.style.width = "100%";
    this.canvas.style.cursor = "default";
    container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d")!;

    this.resizeCanvas();
    window.addEventListener("resize", () => this.resizeCanvas());
    this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
    this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
    this.canvas.addEventListener("mouseup", (e) => this.onMouseUp(e));
    this.canvas.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });

    this.render();
  }

  /** Update notes from external source (e.g. after API call) */
  setNotes(notes: Note[]) {
    this.notes = notes;
    this.render();
  }

  /** Set region from external source (e.g. waveform region selection) */
  setRegion(region: { startSec: number; endSec: number } | null) {
    this.region = region;
    this.render();
  }

  private resizeCanvas() {
    const rect = this.canvas.parentElement!.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = (this.viewport.visiblePitchRange * NOTE_HEIGHT_PX) * dpr;
    this.canvas.style.height = `${this.viewport.visiblePitchRange * NOTE_HEIGHT_PX}px`;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.render();
  }

  private get canvasWidth(): number {
    return this.canvas.width / (window.devicePixelRatio || 1);
  }

  private get canvasHeight(): number {
    return this.canvas.height / (window.devicePixelRatio || 1);
  }

  private timeToX(sec: number): number {
    return KEY_LABEL_WIDTH + (sec - this.viewport.scrollX) / this.viewport.secPerPx;
  }

  private xToTime(x: number): number {
    return (x - KEY_LABEL_WIDTH) * this.viewport.secPerPx + this.viewport.scrollX;
  }

  private pitchToY(midi: number): number {
    const topPitch = this.viewport.scrollY + this.viewport.visiblePitchRange;
    return (topPitch - midi - 1) * NOTE_HEIGHT_PX;
  }

  private yToPitch(y: number): number {
    const topPitch = this.viewport.scrollY + this.viewport.visiblePitchRange;
    return topPitch - Math.floor(y / NOTE_HEIGHT_PX) - 1;
  }

  // --- Rendering ---

  private render() {
    const w = this.canvasWidth;
    const h = this.canvasHeight;
    const ctx = this.ctx;

    // Background
    ctx.fillStyle = this.theme.background;
    ctx.fillRect(0, 0, w, h);

    // Pitch rows
    const topPitch = this.viewport.scrollY + this.viewport.visiblePitchRange;
    for (let p = this.viewport.scrollY; p < topPitch; p++) {
      const y = this.pitchToY(p);
      ctx.fillStyle = isBlackKey(p) ? this.theme.blackRow : this.theme.whiteRow;
      ctx.fillRect(KEY_LABEL_WIDTH, y, w - KEY_LABEL_WIDTH, NOTE_HEIGHT_PX);
      // Grid line
      ctx.strokeStyle = this.theme.gridLine;
      ctx.beginPath();
      ctx.moveTo(KEY_LABEL_WIDTH, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Time grid (every second = beat line, every 0.25s = sub-grid)
    const startTime = this.viewport.scrollX;
    const endTime = this.xToTime(w);
    for (let t = Math.floor(startTime); t <= Math.ceil(endTime); t += 0.25) {
      const x = this.timeToX(t);
      if (x < KEY_LABEL_WIDTH) continue;
      ctx.strokeStyle = t % 1 === 0 ? this.theme.gridLineBeat : this.theme.gridLine;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
      // Time label at full seconds
      if (t % 1 === 0) {
        ctx.fillStyle = this.theme.textColor;
        ctx.font = "10px sans-serif";
        ctx.fillText(`${t}s`, x + 2, h - 4);
      }
    }

    // Region highlight
    if (this.region) {
      const rx = this.timeToX(this.region.startSec);
      const rw = this.timeToX(this.region.endSec) - rx;
      ctx.fillStyle = this.theme.regionColor;
      ctx.fillRect(rx, 0, rw, h);
    }

    // Notes
    for (const note of this.notes) {
      const x = this.timeToX(note.start_sec);
      const y = this.pitchToY(note.pitch_midi);
      const noteW = Math.max(MIN_NOTE_WIDTH_PX, (note.end_sec - note.start_sec) / this.viewport.secPerPx);
      const selected = this.selectedNoteIds.has(note.id);

      ctx.fillStyle = selected ? this.theme.noteSelectedColor : this.theme.noteColor;
      ctx.fillRect(x, y + 1, noteW, NOTE_HEIGHT_PX - 2);
      ctx.strokeStyle = this.theme.noteBorder;
      ctx.strokeRect(x, y + 1, noteW, NOTE_HEIGHT_PX - 2);
    }

    // Key labels (left column)
    ctx.fillStyle = this.theme.keyLabelBg;
    ctx.fillRect(0, 0, KEY_LABEL_WIDTH, h);
    for (let p = this.viewport.scrollY; p < topPitch; p++) {
      const y = this.pitchToY(p);
      ctx.fillStyle = this.theme.textColor;
      ctx.font = "10px monospace";
      ctx.fillText(midiToNoteName(p), 4, y + NOTE_HEIGHT_PX - 4);
    }
  }

  // --- Mouse interactions ---

  private noteAt(x: number, y: number): { note: Note; edge: "left" | "right" | "body" } | null {
    const time = this.xToTime(x);
    const pitch = this.yToPitch(y);
    const edgeThresholdSec = this.viewport.secPerPx * 6; // 6px threshold

    for (const note of this.notes) {
      if (note.pitch_midi !== pitch) continue;
      if (time < note.start_sec || time > note.end_sec) continue;
      if (time - note.start_sec < edgeThresholdSec) return { note, edge: "left" };
      if (note.end_sec - time < edgeThresholdSec) return { note, edge: "right" };
      return { note, edge: "body" };
    }
    return null;
  }

  private onMouseDown(e: MouseEvent) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (x < KEY_LABEL_WIDTH) return; // clicked on key labels

    const hit = this.noteAt(x, y);
    if (hit) {
      // Start dragging a note
      this.selectedNoteIds = new Set([hit.note.id]);
      const dragType = hit.edge === "body" ? "move"
        : hit.edge === "left" ? "resize-left" : "resize-right";
      this.drag = {
        type: dragType,
        noteId: hit.note.id,
        startMouseX: x,
        startMouseY: y,
        origPitch: hit.note.pitch_midi,
        origStartSec: hit.note.start_sec,
        origEndSec: hit.note.end_sec,
      };
      this.render();
    } else {
      // Start region selection
      this.selectedNoteIds.clear();
      this.regionDrag = { startX: x, currentX: x };
      this.region = null;
      this.render();
    }
  }

  private onMouseMove(e: MouseEvent) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (this.drag) {
      const note = this.notes.find((n) => n.id === this.drag!.noteId);
      if (!note) return;

      const deltaPitch = this.yToPitch(y) - this.yToPitch(this.drag.startMouseY);
      const deltaTime = this.xToTime(x) - this.xToTime(this.drag.startMouseX);

      if (this.drag.type === "move") {
        note.pitch_midi = Math.max(0, Math.min(127, this.drag.origPitch + deltaPitch));
        note.start_sec = Math.max(0, this.drag.origStartSec + deltaTime);
        note.end_sec = note.start_sec + (this.drag.origEndSec - this.drag.origStartSec);
      } else if (this.drag.type === "resize-left") {
        note.start_sec = Math.max(0, Math.min(note.end_sec - 0.05, this.drag.origStartSec + deltaTime));
      } else if (this.drag.type === "resize-right") {
        note.end_sec = Math.max(note.start_sec + 0.05, this.drag.origEndSec + deltaTime);
      }
      this.render();

    } else if (this.regionDrag) {
      this.regionDrag.currentX = x;
      const startSec = this.xToTime(Math.min(this.regionDrag.startX, x));
      const endSec = this.xToTime(Math.max(this.regionDrag.startX, x));
      this.region = { startSec: Math.max(0, startSec), endSec: Math.min(this.durationSec, endSec) };
      this.render();

    } else {
      // Update cursor based on what's under mouse
      const hit = this.noteAt(x, y);
      if (hit?.edge === "left" || hit?.edge === "right") {
        this.canvas.style.cursor = "ew-resize";
      } else if (hit?.edge === "body") {
        this.canvas.style.cursor = "grab";
      } else {
        this.canvas.style.cursor = "crosshair";
      }
    }
  }

  private async onMouseUp(_e: MouseEvent) {
    if (this.drag) {
      // Persist the note change via API
      const note = this.notes.find((n) => n.id === this.drag!.noteId);
      if (note) {
        try {
          await updateNote(this.trackId, note.id, {
            pitch_midi: note.pitch_midi,
            start_sec: note.start_sec,
            end_sec: note.end_sec,
          });
          this.onNotesChange(this.notes);
        } catch (err) {
          console.error("Failed to update note:", err);
        }
      }
      this.drag = null;
    }

    if (this.regionDrag) {
      this.regionDrag = null;
      if (this.region) {
        this.onRegionChange(this.region);
      }
    }
  }

  private onWheel(e: WheelEvent) {
    e.preventDefault();
    if (e.shiftKey) {
      // Horizontal scroll (pan timeline)
      this.viewport.scrollX += e.deltaY * this.viewport.secPerPx * 2;
      this.viewport.scrollX = Math.max(0, this.viewport.scrollX);
    } else if (e.ctrlKey || e.metaKey) {
      // Zoom
      const factor = e.deltaY > 0 ? 1.1 : 0.9;
      this.viewport.secPerPx *= factor;
      this.viewport.secPerPx = Math.max(0.001, Math.min(0.1, this.viewport.secPerPx));
    } else {
      // Vertical scroll (pan pitch)
      const deltaPitch = e.deltaY > 0 ? -2 : 2;
      this.viewport.scrollY = Math.max(0, Math.min(108, this.viewport.scrollY + deltaPitch));
    }
    this.render();
  }

  destroy() {
    this.canvas.remove();
  }
}
```

**Step 4: Commit**

```bash
git add frontend/src/lib/canvas-utils.ts frontend/src/components/piano-roll.ts frontend/src/api.ts
git commit -m "feat: canvas-based piano roll with drag-to-edit and region selection"
```

---

## Task 5: Integrate Piano Roll into Editor View

**Files:**
- Modify: `frontend/src/components/waveform.ts`

Update the editor view to:
1. Add WaveSurfer.js Regions plugin for visual region selection on the waveform
2. Mount the PianoRoll canvas below the waveform
3. Sync region selection between waveform and piano roll (bidirectional)
4. Add "Play Region" button that uses the region from either source
5. Add status bar showing selected note info and region bounds

**Step 1: Install WaveSurfer regions plugin**

```bash
cd frontend && npm install wavesurfer.js  # regions plugin is included in v7+
```

**Step 2: Update editor view**

Key changes to `renderEditorView()`:

```typescript
// In frontend/src/components/waveform.ts — updated renderEditorView

import RegionsPlugin from "wavesurfer.js/dist/plugins/regions";
import { PianoRoll } from "./piano-roll";
import { extractMidi, getNotes, synthesize, playbackUrl, originalUrl, regionUrl } from "../api";

export function renderEditorView(container: HTMLElement) {
  const { activeTrackId, tracks } = getState();
  if (!activeTrackId) { /* ... same as Phase 2.5 ... */ return; }

  const track = tracks.find((t) => t.track_id === activeTrackId);

  container.innerHTML = `
    <div class="card">
      <label>Track: </label>
      <select id="track-select">
        ${tracks.map((t) => `<option value="${t.track_id}" ${t.track_id === activeTrackId ? "selected" : ""}>${t.filename} (${t.duration_sec.toFixed(1)}s)</option>`).join("")}
      </select>
    </div>
    <div id="toolbar-mount"></div>
    <div class="card">
      <h3>Waveform</h3>
      <div id="waveform"></div>
    </div>
    <div class="card">
      <h3>Piano Roll</h3>
      <div id="piano-roll-container"></div>
    </div>
    <div id="status-bar" class="card" style="font-family: var(--font-mono); font-size: 0.85rem;">
      Ready
    </div>
  `;

  const statusBar = document.getElementById("status-bar")!;
  let currentNotes: Note[] = [];
  let pianoRoll: PianoRoll | null = null;
  let currentRegion: { startSec: number; endSec: number } | null = null;

  // WaveSurfer with regions plugin
  const regions = RegionsPlugin.create();
  const ws = WaveSurfer.create({
    container: "#waveform",
    waveColor: "#4a4a6a",
    progressColor: "#e94560",
    cursorColor: "#e94560",
    height: 80,
    url: originalUrl(activeTrackId),
    plugins: [regions],
  });

  // Enable drag-to-create region on waveform
  regions.enableDragSelection({ color: "rgba(233, 69, 96, 0.2)" });
  regions.on("region-created", (region) => {
    // Remove any previous regions (only one active region at a time)
    regions.getRegions().forEach((r) => { if (r.id !== region.id) r.remove(); });
    currentRegion = { startSec: region.start, endSec: region.end };
    statusBar.textContent = `Region: ${region.start.toFixed(2)}s — ${region.end.toFixed(2)}s`;
    pianoRoll?.setRegion(currentRegion);
  });
  regions.on("region-updated", (region) => {
    currentRegion = { startSec: region.start, endSec: region.end };
    statusBar.textContent = `Region: ${region.start.toFixed(2)}s — ${region.end.toFixed(2)}s`;
    pianoRoll?.setRegion(currentRegion);
  });

  // Toolbar — add "Play Region" button
  renderToolbar(document.getElementById("toolbar-mount")!, {
    onPlay: () => ws.play(),
    onPause: () => ws.pause(),
    onStop: () => ws.stop(),
    onExtract: async () => {
      statusBar.textContent = "Extracting MIDI (this may take ~30s)...";
      try {
        const result = await extractMidi(activeTrackId);
        currentNotes = result.notes;
        mountPianoRoll(currentNotes);
        statusBar.textContent = `Extracted ${result.notes.length} notes.`;
      } catch (e) {
        statusBar.textContent = `Extract failed: ${e}`;
      }
    },
    onSynthesize: async () => {
      statusBar.textContent = "Synthesizing...";
      try {
        const result = await synthesize(activeTrackId);
        ws.load(result.playback_url);
        statusBar.textContent = "Synthesized.";
      } catch (e) {
        statusBar.textContent = `Synthesize failed: ${e}`;
      }
    },
  });

  // Add "Play Region" button to toolbar
  const toolbar = document.getElementById("toolbar-mount")!.querySelector(".toolbar")!;
  const playRegionBtn = document.createElement("button");
  playRegionBtn.textContent = "Play Region";
  playRegionBtn.addEventListener("click", () => {
    if (!currentRegion) {
      statusBar.textContent = "No region selected. Drag on waveform or piano roll.";
      return;
    }
    const audio = new Audio(regionUrl(activeTrackId, currentRegion.startSec, currentRegion.endSec));
    audio.play();
  });
  toolbar.appendChild(playRegionBtn);

  function mountPianoRoll(notes: Note[]) {
    pianoRoll?.destroy();
    const prContainer = document.getElementById("piano-roll-container")!;
    prContainer.innerHTML = "";
    pianoRoll = new PianoRoll(prContainer, {
      trackId: activeTrackId,
      notes,
      durationSec: track?.duration_sec ?? 30,
      onNotesChange: (updatedNotes) => {
        currentNotes = updatedNotes;
        statusBar.textContent = "Note updated. Click Synthesize to hear changes.";
      },
      onRegionChange: (region) => {
        currentRegion = region;
        // Sync to waveform
        regions.getRegions().forEach((r) => r.remove());
        if (region) {
          regions.addRegion({
            start: region.startSec,
            end: region.endSec,
            color: "rgba(233, 69, 96, 0.2)",
            drag: true,
            resize: true,
          });
          statusBar.textContent = `Region: ${region.startSec.toFixed(2)}s — ${region.endSec.toFixed(2)}s`;
        }
      },
      onRequestSynthesize: async () => {
        statusBar.textContent = "Synthesizing...";
        const result = await synthesize(activeTrackId);
        ws.load(result.playback_url);
        statusBar.textContent = "Synthesized.";
      },
    });
  }

  // Load existing notes if available
  getNotes(activeTrackId).then((data) => {
    if (data.notes?.length) {
      currentNotes = data.notes;
      mountPianoRoll(currentNotes);
    }
  }).catch(() => {});
}
```

**Step 3: Verify interactions**

1. Upload a track → Extract MIDI → piano roll appears below waveform
2. Click a note → it highlights
3. Drag a note vertically → pitch changes, persists via API
4. Drag a note horizontally → timing changes, persists via API
5. Drag note edge → duration changes
6. Click+drag empty area in piano roll → region appears, syncs to waveform
7. Click+drag on waveform → region appears, syncs to piano roll
8. Click "Play Region" → plays only the selected time range
9. Scroll wheel → zoom/pan timeline
10. Click Synthesize → hear the edited notes

**Step 4: Commit**

```bash
git add frontend/src/components/waveform.ts
git commit -m "feat: integrate piano roll with waveform, synced region selection"
```

---

## Task 6: Extend Integration Test

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
- [ ] Piano roll renders notes as colored rectangles on pitch × time grid
- [ ] Click note → selects it, status bar shows pitch and duration
- [ ] Drag note vertically → pitch changes, persists to backend
- [ ] Drag note horizontally → timing changes, persists to backend
- [ ] Drag note edge → duration changes, persists to backend
- [ ] Click+drag empty area → region selection appears
- [ ] Region selection synced between waveform and piano roll (bidirectional)
- [ ] "Play Region" plays only the selected time range
- [ ] Scroll wheel: zoom (Ctrl+scroll), pan time (Shift+scroll), pan pitch (scroll)
- [ ] Synthesize updates waveform with edited notes
- [ ] Individual note edit via `PUT /midi/{id}/notes/{note_id}` still works
- [ ] Bulk region edit via `PUT /midi/{id}/region` still works
