export type AudioSource = "original" | "synth";

export interface ToolbarCallbacks {
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onExtract: () => void;
  onSynthesize: () => void;
  onPlayRegion: () => void;
  onSourceChange: (source: AudioSource) => void;
  onInstrumentChange: (instrument: string) => void;
  onTrackChange: (trackId: string) => void;
}

export interface ToolbarOptions {
  tracks: Array<{ track_id: string; name: string }>;
  activeTrackId: string;
  instruments: string[];
  defaultInstrument: string;
}

export interface ToolbarControls {
  setSource: (source: AudioSource) => void;
  setSynthEnabled: (enabled: boolean) => void;
  setRegionEnabled: (enabled: boolean) => void;
  getSource: () => AudioSource;
  getInstrument: () => string;
}

export function renderToolbar(
  container: HTMLElement,
  options: ToolbarOptions,
  callbacks: ToolbarCallbacks,
): ToolbarControls {
  let currentSource: AudioSource = "original";

  function escapeHtml(s: string): string {
    const el = document.createElement("span");
    el.textContent = s;
    return el.innerHTML;
  }

  container.innerHTML = `
    <div class="control-bar">
      <div class="control-row">
        <div class="control-group">
          <label for="tb-track">Track</label>
          <select id="tb-track">
            ${options.tracks.map((t) =>
              `<option value="${t.track_id}" ${t.track_id === options.activeTrackId ? "selected" : ""}>${escapeHtml(t.name)}</option>`
            ).join("")}
          </select>
        </div>
        <div class="control-divider"></div>
        <div class="control-group">
          <button class="btn-transport" id="tb-play" title="Play">&#9654;</button>
          <button class="btn-transport" id="tb-pause" title="Pause">&#9208;</button>
          <button class="btn-transport" id="tb-stop" title="Stop">&#9209;</button>
        </div>
        <div class="control-divider"></div>
        <div class="control-group source-toggle">
          <input type="radio" name="source" id="src-original" value="original" checked />
          <label for="src-original">Original</label>
          <input type="radio" name="source" id="src-synth" value="synth" disabled />
          <label for="src-synth">Synth</label>
        </div>
        <div class="control-divider"></div>
        <div class="control-group">
          <button class="btn-action" id="tb-region" disabled>Play Region</button>
        </div>
      </div>
      <div class="control-row">
        <div class="control-group">
          <label for="tb-instrument">Instrument</label>
          <select id="tb-instrument">
            ${options.instruments.map((inst) =>
              `<option value="${escapeHtml(inst)}" ${inst === options.defaultInstrument ? "selected" : ""}>${escapeHtml(inst)}</option>`
            ).join("")}
          </select>
        </div>
        <div class="control-divider"></div>
        <div class="control-group">
          <button class="btn-action" id="tb-extract">Extract MIDI</button>
          <button class="btn-action primary" id="tb-synth">Synthesize</button>
        </div>
      </div>
    </div>
  `;

  // Wire events
  container.querySelector("#tb-play")!.addEventListener("click", callbacks.onPlay);
  container.querySelector("#tb-pause")!.addEventListener("click", callbacks.onPause);
  container.querySelector("#tb-stop")!.addEventListener("click", callbacks.onStop);
  container.querySelector("#tb-extract")!.addEventListener("click", callbacks.onExtract);
  container.querySelector("#tb-synth")!.addEventListener("click", callbacks.onSynthesize);
  container.querySelector("#tb-region")!.addEventListener("click", callbacks.onPlayRegion);

  container.querySelectorAll<HTMLInputElement>('input[name="source"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.checked) {
        currentSource = radio.value as AudioSource;
        callbacks.onSourceChange(currentSource);
      }
    });
  });

  container.querySelector("#tb-track")!.addEventListener("change", (e) => {
    callbacks.onTrackChange((e.target as HTMLSelectElement).value);
  });

  container.querySelector("#tb-instrument")!.addEventListener("change", (e) => {
    callbacks.onInstrumentChange((e.target as HTMLSelectElement).value);
  });

  // Return control API
  return {
    setSource(source: AudioSource) {
      currentSource = source;
      const radio = container.querySelector(`#src-${source}`) as HTMLInputElement;
      if (radio) radio.checked = true;
    },
    setSynthEnabled(enabled: boolean) {
      const radio = container.querySelector("#src-synth") as HTMLInputElement;
      if (radio) radio.disabled = !enabled;
    },
    setRegionEnabled(enabled: boolean) {
      const btn = container.querySelector("#tb-region") as HTMLButtonElement;
      if (btn) btn.disabled = !enabled;
    },
    getSource() {
      return currentSource;
    },
    getInstrument() {
      return (container.querySelector("#tb-instrument") as HTMLSelectElement)?.value ?? options.defaultInstrument;
    },
  };
}
