export interface TrackInfo {
  track_id: string;
  name: string;
  duration_sec: number;
  sample_rate: number;
}

export interface Note {
  id: string;
  track_id: string;
  pitch_midi: number;
  start_sec: number;
  end_sec: number;
  velocity: number;
}

export interface WaveformData {
  times: number[];
  amplitudes: number[];
}

export interface InstrumentList {
  instruments: string[];
  default: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(path, options);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

export async function uploadTrack(file: File, name: string): Promise<TrackInfo> {
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  return request("/audio/upload", { method: "POST", body: form });
}

export async function recordTrack(blob: Blob, name: string): Promise<TrackInfo> {
  const form = new FormData();
  form.append("file", blob, "recording.wav");
  form.append("name", name);
  return request("/audio/record", { method: "POST", body: form });
}

export async function extractMidi(trackId: string): Promise<{ notes: Note[] }> {
  return request(`/midi/${trackId}/extract`, { method: "POST" });
}

export async function getNotes(trackId: string): Promise<{ notes: Note[] }> {
  return request(`/midi/${trackId}`);
}

export async function updateNote(
  trackId: string,
  noteId: string,
  updates: Partial<Pick<Note, "pitch_midi" | "start_sec" | "end_sec" | "velocity">>
): Promise<Note> {
  return request(`/midi/${trackId}/notes/${noteId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function synthesize(
  trackId: string,
  instrument?: string
): Promise<{ playback_url: string; instrument: string }> {
  const params = instrument ? `?instrument=${encodeURIComponent(instrument)}` : "";
  return request(`/midi/${trackId}/synthesize${params}`, { method: "POST" });
}

export function playbackUrl(trackId: string): string {
  return `/audio/${trackId}/playback`;
}

export async function getWaveform(trackId: string): Promise<WaveformData> {
  return request(`/audio/${trackId}/waveform`);
}

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

export function regionUrl(trackId: string, startSec: number, endSec: number): string {
  return `/audio/${trackId}/region?start_sec=${startSec}&end_sec=${endSec}`;
}

let _cachedInstruments: InstrumentList | null = null;

export async function getInstruments(): Promise<InstrumentList> {
  if (_cachedInstruments) return _cachedInstruments;
  _cachedInstruments = await request<InstrumentList>("/midi/instruments/list");
  return _cachedInstruments;
}
