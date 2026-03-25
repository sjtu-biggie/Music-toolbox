import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions";
import { getState, setState } from "../state";
import {
  extractMidi,
  getNotes,
  synthesize,
  playbackUrl,
  regionUrl,
  getInstruments,
} from "../api";
import { renderToolbar } from "./toolbar";
import type { ToolbarControls, AudioSource } from "./toolbar";
import { PianoRoll } from "./piano-roll";
import type { Note } from "../api";

let activeWaveSurfer: WaveSurfer | null = null;

export function renderEditorView(container: HTMLElement) {
  if (activeWaveSurfer) {
    activeWaveSurfer.destroy();
    activeWaveSurfer = null;
  }

  const { activeTrackId, tracks } = getState();

  if (!activeTrackId) {
    container.innerHTML = `<div class="card"><p>No track selected. Upload or record first.</p></div>`;
    return;
  }

  const trackId: string = activeTrackId;
  const track = tracks.find((t) => t.track_id === trackId);

  // State
  let allNotes: Note[] = [];
  let pianoRoll: PianoRoll | null = null;
  let currentRegion: { startSec: number; endSec: number } | null = null;
  let synthUrl: string | null = null;
  let toolbarControls: ToolbarControls;
  let selectedInstrument = "piano";

  // Layout
  container.innerHTML = `
    <div id="toolbar-mount"></div>
    <div class="editor-canvas">
      <div class="waveform-section">
        <div id="waveform"></div>
      </div>
      <div class="divider"></div>
      <div class="piano-roll-section">
        <div id="piano-roll-container"></div>
      </div>
    </div>
    <div class="status-bar">
      <span class="status-segment status-message" id="status-msg">Ready</span>
      <span class="status-segment" id="status-region">&mdash;</span>
      <span class="status-segment" id="status-notes">&mdash;</span>
    </div>
  `;

  const statusMsg = document.getElementById("status-msg")!;
  const statusRegion = document.getElementById("status-region")!;
  const statusNotes = document.getElementById("status-notes")!;

  function setStatus(msg: string) { statusMsg.textContent = msg; }
  function updateRegionStatus() {
    statusRegion.textContent = currentRegion
      ? `Region: ${currentRegion.startSec.toFixed(2)}s \u2014 ${currentRegion.endSec.toFixed(2)}s`
      : "\u2014";
  }
  function updateNoteCount() {
    statusNotes.textContent = allNotes.length > 0 ? `${allNotes.length} notes` : "\u2014";
  }

  // Load instruments, then render toolbar
  getInstruments().then((instrData) => {
    selectedInstrument = instrData.default;

    toolbarControls = renderToolbar(
      document.getElementById("toolbar-mount")!,
      {
        tracks: tracks.map((t) => ({ track_id: t.track_id, name: t.name })),
        activeTrackId: trackId,
        instruments: instrData.instruments,
        defaultInstrument: instrData.default,
      },
      {
        onPlay: () => ws.play(),
        onPause: () => ws.pause(),
        onStop: () => ws.stop(),
        onExtract: handleExtract,
        onSynthesize: handleSynthesize,
        onPlayRegion: handlePlayRegion,
        onSourceChange: handleSourceChange,
        onInstrumentChange: (inst) => { selectedInstrument = inst; },
        onTrackChange: (newTrackId) => {
          setState({ activeTrackId: newTrackId });
          renderEditorView(container);
        },
      },
    );
  });

  // WaveSurfer
  const regions = RegionsPlugin.create();
  const ws = WaveSurfer.create({
    container: "#waveform",
    waveColor: "#4a4a6a",
    progressColor: "#e94560",
    cursorColor: "#e94560",
    height: 80,
    url: playbackUrl(trackId),
    plugins: [regions],
  });
  activeWaveSurfer = ws;

  // Region selection on waveform
  regions.enableDragSelection({ color: "rgba(233, 69, 96, 0.2)" });
  regions.on("region-created", (region) => {
    regions.getRegions().forEach((r) => { if (r.id !== region.id) r.remove(); });
    currentRegion = { startSec: region.start, endSec: region.end };
    updateRegionStatus();
    toolbarControls?.setRegionEnabled(true);
    pianoRoll?.setRegion(currentRegion);
  });
  regions.on("region-updated", (region) => {
    currentRegion = { startSec: region.start, endSec: region.end };
    updateRegionStatus();
    pianoRoll?.setRegion(currentRegion);
  });

  // Handlers
  async function handleExtract() {
    setStatus("Extracting MIDI (this may take ~30s)...");
    try {
      const result = await extractMidi(trackId);
      allNotes = result.notes;
      updateNoteCount();
      mountPianoRoll(allNotes);
      setStatus(`Extracted ${result.notes.length} notes.`);
    } catch (e) {
      setStatus(`Extract failed: ${e}`);
    }
  }

  async function handleSynthesize() {
    setStatus(`Synthesizing with ${selectedInstrument}...`);
    try {
      const result = await synthesize(trackId, selectedInstrument);
      synthUrl = result.playback_url;
      // Switch to synth source
      toolbarControls?.setSynthEnabled(true);
      toolbarControls?.setSource("synth");
      ws.load(synthUrl);
      setStatus(`Synthesized with ${result.instrument}.`);
    } catch (e) {
      setStatus(`Synthesize failed: ${e}`);
    }
  }

  function handlePlayRegion() {
    if (!currentRegion) {
      setStatus("No region selected. Drag on waveform or piano roll.");
      return;
    }
    // Region always plays original audio (region slicing is from original file)
    const url = regionUrl(trackId, currentRegion.startSec, currentRegion.endSec);
    const audio = new Audio(url);
    audio.play();
  }

  function handleSourceChange(source: AudioSource) {
    if (source === "synth" && synthUrl) {
      ws.load(synthUrl);
    } else {
      ws.load(playbackUrl(trackId));
    }
  }

  // Piano Roll
  function mountPianoRoll(notes: Note[]) {
    pianoRoll?.destroy();
    const prContainer = document.getElementById("piano-roll-container")!;
    prContainer.innerHTML = "";
    pianoRoll = new PianoRoll(prContainer, {
      trackId,
      notes,
      durationSec: track?.duration_sec ?? 30,
      onNotesChange: (updatedNotes) => {
        allNotes = updatedNotes;
        updateNoteCount();
        setStatus("Note updated. Click Synthesize to hear changes.");
      },
      onRegionChange: (region) => {
        currentRegion = region;
        updateRegionStatus();
        toolbarControls?.setRegionEnabled(!!region);
        regions.getRegions().forEach((r) => r.remove());
        if (region) {
          regions.addRegion({
            start: region.startSec,
            end: region.endSec,
            color: "rgba(233, 69, 96, 0.2)",
            drag: true,
            resize: true,
          });
        }
      },
    });
  }

  // Load existing notes if already extracted
  getNotes(trackId)
    .then((data) => {
      if (data.notes?.length) {
        allNotes = data.notes;
        updateNoteCount();
        mountPianoRoll(allNotes);
      }
    })
    .catch(() => {});
}
