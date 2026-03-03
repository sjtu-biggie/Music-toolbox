import { defaultViewport, darkTheme, midiToNoteName, isBlackKey } from "../lib/canvas-utils";
import type { Viewport, PianoRollTheme } from "../lib/canvas-utils";
import { updateNote } from "../api";
import type { Note } from "../api";

const KEY_LABEL_WIDTH = 48;
const NOTE_HEIGHT_PX = 16;
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
  onNotesChange: (notes: Note[]) => void;
  onRegionChange: (region: { startSec: number; endSec: number } | null) => void;
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
  private resizeHandler: () => void;

  constructor(container: HTMLElement, options: PianoRollOptions) {
    this.trackId = options.trackId;
    this.notes = options.notes;
    this.durationSec = options.durationSec;
    this.onNotesChange = options.onNotesChange;
    this.onRegionChange = options.onRegionChange;
    this.viewport = defaultViewport();

    this.canvas = document.createElement("canvas");
    this.canvas.style.width = "100%";
    this.canvas.style.cursor = "default";
    container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d")!;

    this.resizeHandler = () => this.resizeCanvas();
    this.resizeCanvas();
    window.addEventListener("resize", this.resizeHandler);
    this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
    this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
    this.canvas.addEventListener("mouseup", (e) => this.onMouseUp(e));
    this.canvas.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });

    this.render();
  }

  setNotes(notes: Note[]) {
    this.notes = notes;
    this.render();
  }

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

  private render() {
    const w = this.canvasWidth;
    const h = this.canvasHeight;
    const ctx = this.ctx;

    ctx.fillStyle = this.theme.background;
    ctx.fillRect(0, 0, w, h);

    const topPitch = this.viewport.scrollY + this.viewport.visiblePitchRange;
    for (let p = this.viewport.scrollY; p < topPitch; p++) {
      const y = this.pitchToY(p);
      ctx.fillStyle = isBlackKey(p) ? this.theme.blackRow : this.theme.whiteRow;
      ctx.fillRect(KEY_LABEL_WIDTH, y, w - KEY_LABEL_WIDTH, NOTE_HEIGHT_PX);
      ctx.strokeStyle = this.theme.gridLine;
      ctx.beginPath();
      ctx.moveTo(KEY_LABEL_WIDTH, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

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
      if (t % 1 === 0) {
        ctx.fillStyle = this.theme.textColor;
        ctx.font = "10px sans-serif";
        ctx.fillText(`${t}s`, x + 2, h - 4);
      }
    }

    if (this.region) {
      const rx = this.timeToX(this.region.startSec);
      const rw = this.timeToX(this.region.endSec) - rx;
      ctx.fillStyle = this.theme.regionColor;
      ctx.fillRect(rx, 0, rw, h);
    }

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

    ctx.fillStyle = this.theme.keyLabelBg;
    ctx.fillRect(0, 0, KEY_LABEL_WIDTH, h);
    for (let p = this.viewport.scrollY; p < topPitch; p++) {
      const y = this.pitchToY(p);
      ctx.fillStyle = this.theme.textColor;
      ctx.font = "10px monospace";
      ctx.fillText(midiToNoteName(p), 4, y + NOTE_HEIGHT_PX - 4);
    }
  }

  private noteAt(x: number, y: number): { note: Note; edge: "left" | "right" | "body" } | null {
    const time = this.xToTime(x);
    const pitch = this.yToPitch(y);
    const edgeThresholdSec = this.viewport.secPerPx * 6;

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

    if (x < KEY_LABEL_WIDTH) return;

    const hit = this.noteAt(x, y);
    if (hit) {
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
      this.viewport.scrollX += e.deltaY * this.viewport.secPerPx * 2;
      this.viewport.scrollX = Math.max(0, this.viewport.scrollX);
    } else if (e.ctrlKey || e.metaKey) {
      const factor = e.deltaY > 0 ? 1.1 : 0.9;
      this.viewport.secPerPx *= factor;
      this.viewport.secPerPx = Math.max(0.001, Math.min(0.1, this.viewport.secPerPx));
    } else {
      const deltaPitch = e.deltaY > 0 ? -2 : 2;
      this.viewport.scrollY = Math.max(0, Math.min(108, this.viewport.scrollY + deltaPitch));
    }
    this.render();
  }

  destroy() {
    window.removeEventListener("resize", this.resizeHandler);
    this.canvas.remove();
  }
}
