/** Convert MIDI pitch number to note name (e.g. 60 -> "C4") */
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
    scrollY: 48,
    secPerPx: 0.01,
    visiblePitchRange: 36,
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
