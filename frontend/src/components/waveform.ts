import WaveSurfer from "wavesurfer.js";
import { getState, setState } from "../state";
import { extractMidi, getNotes, synthesize, playbackUrl } from "../api";
import { renderToolbar } from "./toolbar";
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

  container.innerHTML = `
    <div class="card">
      <label>Track: </label>
      <select id="track-select">
        ${tracks.map((t) =>
          `<option value="${t.track_id}" ${t.track_id === activeTrackId ? "selected" : ""}>
            ${t.filename} (${t.duration_sec.toFixed(1)}s)
          </option>`
        ).join("")}
      </select>
    </div>
    <div id="toolbar-mount"></div>
    <div class="card">
      <h3>Waveform</h3>
      <div id="waveform"></div>
    </div>
    <div class="card">
      <h3>Notes</h3>
      <div id="note-list"><p>Click "Extract MIDI" to see notes.</p></div>
    </div>
    <div id="status-bar" class="card" style="font-family: var(--font-mono); font-size: 0.85rem;">
      Ready
    </div>
  `;

  const statusBar = document.getElementById("status-bar")!;

  const ws = WaveSurfer.create({
    container: "#waveform",
    waveColor: "#4a4a6a",
    progressColor: "#e94560",
    cursorColor: "#e94560",
    height: 80,
    url: playbackUrl(activeTrackId),
  });
  activeWaveSurfer = ws;

  renderToolbar(document.getElementById("toolbar-mount")!, {
    onPlay: () => ws.play(),
    onPause: () => ws.pause(),
    onStop: () => { ws.stop(); },
    onExtract: async () => {
      statusBar.textContent = "Extracting MIDI (this may take ~30s)...";
      try {
        const result = await extractMidi(activeTrackId);
        renderNoteList(result.notes);
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
        statusBar.textContent = "Synthesized. Playing back.";
      } catch (e) {
        statusBar.textContent = `Synthesize failed: ${e}`;
      }
    },
  });

  document.getElementById("track-select")!.addEventListener("change", (e) => {
    const select = e.target as HTMLSelectElement;
    setState({ activeTrackId: select.value });
    renderEditorView(container);
  });

  function renderNoteList(notes: Note[]) {
    const noteList = document.getElementById("note-list")!;
    if (notes.length === 0) {
      noteList.innerHTML = "<p>No notes found.</p>";
      return;
    }
    const display = notes.slice(0, 50);
    noteList.innerHTML = `
      <table style="width:100%; font-size:0.85rem;">
        <thead>
          <tr><th>Pitch</th><th>Start (s)</th><th>End (s)</th><th>Velocity</th></tr>
        </thead>
        <tbody>
          ${display.map((n) => `
            <tr>
              <td>${n.pitch_midi}</td>
              <td>${n.start_sec.toFixed(2)}</td>
              <td>${n.end_sec.toFixed(2)}</td>
              <td>${n.velocity}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      ${notes.length > 50 ? `<p>${notes.length - 50} more notes not shown.</p>` : ""}
    `;
  }

  getNotes(activeTrackId).then((data) => {
    if (data.notes?.length) renderNoteList(data.notes);
  }).catch(() => {});
}
