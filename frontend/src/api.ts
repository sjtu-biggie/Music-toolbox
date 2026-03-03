export interface TrackInfo {
  track_id: string;
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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(path, options);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

export async function uploadTrack(file: File): Promise<TrackInfo> {
  const form = new FormData();
  form.append("file", file);
  return request("/audio/upload", { method: "POST", body: form });
}

export async function recordTrack(blob: Blob, filename = "recording.wav"): Promise<TrackInfo> {
  const form = new FormData();
  form.append("file", blob, filename);
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
  updates: Partial<Pick<Note, "pitch_midi" | "start_sec" | "end_sec">>
): Promise<Note> {
  return request(`/midi/${trackId}/notes/${noteId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function synthesize(trackId: string): Promise<{ playback_url: string }> {
  return request(`/midi/${trackId}/synthesize`, { method: "POST" });
}

export function playbackUrl(trackId: string): string {
  return `/audio/${trackId}/playback`;
}

export async function getWaveform(trackId: string): Promise<WaveformData> {
  return request(`/audio/${trackId}/waveform`);
}
