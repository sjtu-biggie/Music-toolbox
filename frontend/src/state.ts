type Listener = () => void;

export interface AppState {
  tracks: Array<{ track_id: string; filename: string; duration_sec: number }>;
  activeTrackId: string | null;
}

const state: AppState = {
  tracks: [],
  activeTrackId: null,
};

const listeners: Listener[] = [];

export function getState(): Readonly<AppState> {
  return state;
}

export function setState(updates: Partial<AppState>) {
  Object.assign(state, updates);
  listeners.forEach((fn) => fn());
}

export function subscribe(fn: Listener): () => void {
  listeners.push(fn);
  return () => {
    const idx = listeners.indexOf(fn);
    if (idx >= 0) listeners.splice(idx, 1);
  };
}
