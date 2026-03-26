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

export async function createNote(
  trackId: string,
  note: { pitch_midi: number; start_sec: number; end_sec: number; velocity?: number }
): Promise<Note> {
  return request(`/midi/${trackId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(note),
  });
}

export async function deleteNote(trackId: string, noteId: string): Promise<{ deleted: string }> {
  return request(`/midi/${trackId}/notes/${noteId}`, { method: "DELETE" });
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

// AI modification types and methods

export interface AIJob {
  job_id: string;
  status: "pending" | "running" | "done" | "failed";
  result_url?: string;
  error_msg?: string;
}

export async function requestAIModify(
  trackId: string,
  mode: "style" | "melody" | "accompaniment",
  prompt: string,
  startSec: number,
  endSec: number,
  provider: "local" | "replicate"
): Promise<{ job_id: string }> {
  return request(`/ai/${trackId}/modify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode, prompt, start_sec: startSec, end_sec: endSec, provider,
    }),
  });
}

export async function pollJob(jobId: string): Promise<AIJob> {
  return request(`/ai/jobs/${jobId}`);
}

export function aiResultUrl(jobId: string): string {
  return `/ai/jobs/${jobId}/result`;
}

export async function spliceAIResult(
  trackId: string, jobId: string, forceDurationMatch = false
): Promise<{ spliced_track_id: string }> {
  return request(`/ai/${trackId}/splice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, force_duration_match: forceDurationMatch }),
  });
}
