export interface ToolbarCallbacks {
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onExtract: () => void;
  onSynthesize: () => void;
}

export function renderToolbar(container: HTMLElement, callbacks: ToolbarCallbacks) {
  const div = document.createElement("div");
  div.className = "card toolbar";
  div.style.display = "flex";
  div.style.gap = "0.5rem";
  div.style.alignItems = "center";
  div.innerHTML = `
    <button id="tb-play" title="Play">Play</button>
    <button id="tb-pause" title="Pause">Pause</button>
    <button id="tb-stop" title="Stop">Stop</button>
    <span style="flex:1"></span>
    <button id="tb-extract">Extract MIDI</button>
    <button id="tb-synth">Synthesize</button>
  `;
  container.appendChild(div);

  div.querySelector("#tb-play")!.addEventListener("click", callbacks.onPlay);
  div.querySelector("#tb-pause")!.addEventListener("click", callbacks.onPause);
  div.querySelector("#tb-stop")!.addEventListener("click", callbacks.onStop);
  div.querySelector("#tb-extract")!.addEventListener("click", callbacks.onExtract);
  div.querySelector("#tb-synth")!.addEventListener("click", callbacks.onSynthesize);
}
