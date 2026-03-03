import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions";
import { getState } from "../state";
import {
  extractMidi,
  getNotes,
  synthesize,
  updateNote,
  playbackUrl,
  regionUrl,
  getInstruments,
} from "../api";
import { renderToolbar } from "./toolbar";
import { PianoRoll } from "./piano-roll";
import type { Note } from "../api";

let activeWaveSurfer: WaveSurfer | null = null;

const NOTES_PER_PAGE = 50;

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

  container.innerHTML = `
    <div class="card">
      <label>Track: </label>
      <select id="track-select">
        ${tracks.map((t) =>
          `<option value="${t.track_id}" ${t.track_id === trackId ? "selected" : ""}>
            ${t.name} (${t.duration_sec.toFixed(1)}s)
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
      <h3>Piano Roll</h3>
      <div id="piano-roll-container"></div>
    </div>
    <div class="card" id="instrument-card">
      <label for="instrument-select">Instrument: </label>
      <select id="instrument-select"><option>Loading...</option></select>
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
  const instrumentSelect = document.getElementById("instrument-select") as HTMLSelectElement;

  getInstruments().then((data) => {
    instrumentSelect.innerHTML = data.instruments
      .map(
        (inst) =>
          `<option value="${inst}" ${inst === data.default ? "selected" : ""}>${inst}</option>`
      )
      .join("");
  });

  // WaveSurfer with regions plugin
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

  let allNotes: Note[] = [];
  let notePage = 0;
  let notesModified = false;
  let pianoRoll: PianoRoll | null = null;
  let currentRegion: { startSec: number; endSec: number } | null = null;

  // Enable drag-to-create region on waveform
  regions.enableDragSelection({ color: "rgba(233, 69, 96, 0.2)" });
  regions.on("region-created", (region) => {
    regions.getRegions().forEach((r) => { if (r.id !== region.id) r.remove(); });
    currentRegion = { startSec: region.start, endSec: region.end };
    statusBar.textContent = `Region: ${region.start.toFixed(2)}s — ${region.end.toFixed(2)}s`;
    pianoRoll?.setRegion(currentRegion);
  });
  regions.on("region-updated", (region) => {
    currentRegion = { startSec: region.start, endSec: region.end };
    statusBar.textContent = `Region: ${region.start.toFixed(2)}s — ${region.end.toFixed(2)}s`;
    pianoRoll?.setRegion(currentRegion);
  });

  renderToolbar(document.getElementById("toolbar-mount")!, {
    onPlay: () => ws.play(),
    onPause: () => ws.pause(),
    onStop: () => {
      ws.stop();
    },
    onExtract: async () => {
      statusBar.textContent = "Extracting MIDI (this may take ~30s)...";
      try {
        const result = await extractMidi(trackId);
        allNotes = result.notes;
        notePage = 0;
        notesModified = false;
        renderNoteList();
        mountPianoRoll(allNotes);
        statusBar.textContent = `Extracted ${result.notes.length} notes.`;
      } catch (e) {
        statusBar.textContent = `Extract failed: ${e}`;
      }
    },
    onSynthesize: async () => {
      const instrument = instrumentSelect.value;
      statusBar.textContent = `Synthesizing with ${instrument}...`;
      try {
        const result = await synthesize(trackId, instrument);
        ws.load(result.playback_url);
        notesModified = false;
        statusBar.textContent = `Synthesized with ${result.instrument}. Playing back.`;
      } catch (e) {
        statusBar.textContent = `Synthesize failed: ${e}`;
      }
    },
  });

  // Add "Play Region" button to toolbar
  const toolbar = document.getElementById("toolbar-mount")!.querySelector(".toolbar");
  if (toolbar) {
    const playRegionBtn = document.createElement("button");
    playRegionBtn.textContent = "Play Region";
    playRegionBtn.addEventListener("click", () => {
      if (!currentRegion) {
        statusBar.textContent = "No region selected. Drag on waveform or piano roll.";
        return;
      }
      const audio = new Audio(regionUrl(trackId, currentRegion.startSec, currentRegion.endSec));
      audio.play();
    });
    toolbar.appendChild(playRegionBtn);
  }

  document.getElementById("track-select")!.addEventListener("change", (e) => {
    const select = e.target as HTMLSelectElement;
    const { tracks: currentTracks } = getState();
    const newState: Record<string, unknown> = { activeTrackId: select.value };
    newState.tracks = currentTracks;
    import("../state").then(({ setState }) => {
      setState({ activeTrackId: select.value });
      renderEditorView(container);
    });
  });

  function mountPianoRoll(notes: Note[]) {
    pianoRoll?.destroy();
    const prContainer = document.getElementById("piano-roll-container")!;
    prContainer.innerHTML = "";
    pianoRoll = new PianoRoll(prContainer, {
      trackId: trackId,
      notes,
      durationSec: track?.duration_sec ?? 30,
      onNotesChange: (updatedNotes) => {
        allNotes = updatedNotes;
        notesModified = true;
        renderNoteList();
        statusBar.textContent = "Note updated. Click Synthesize to hear changes.";
      },
      onRegionChange: (region) => {
        currentRegion = region;
        regions.getRegions().forEach((r) => r.remove());
        if (region) {
          regions.addRegion({
            start: region.startSec,
            end: region.endSec,
            color: "rgba(233, 69, 96, 0.2)",
            drag: true,
            resize: true,
          });
          statusBar.textContent = `Region: ${region.startSec.toFixed(2)}s — ${region.endSec.toFixed(2)}s`;
        }
      },
      onRequestSynthesize: async () => {
        const instrument = instrumentSelect.value;
        statusBar.textContent = `Synthesizing with ${instrument}...`;
        const result = await synthesize(trackId, instrument);
        ws.load(result.playback_url);
        notesModified = false;
        statusBar.textContent = `Synthesized with ${result.instrument}.`;
      },
    });
  }

  function renderNoteList() {
    const noteList = document.getElementById("note-list")!;
    if (allNotes.length === 0) {
      noteList.innerHTML = "<p>No notes found.</p>";
      return;
    }
    const totalPages = Math.ceil(allNotes.length / NOTES_PER_PAGE);
    const start = notePage * NOTES_PER_PAGE;
    const display = allNotes.slice(start, start + NOTES_PER_PAGE);

    noteList.innerHTML = `
      ${notesModified ? '<p style="color: var(--accent);">Notes modified — re-synthesize to hear changes.</p>' : ""}
      <table style="width:100%; font-size:0.85rem;">
        <thead>
          <tr><th>Pitch</th><th>Start (s)</th><th>End (s)</th><th>Velocity</th><th></th></tr>
        </thead>
        <tbody>
          ${display.map((n, i) => `
            <tr data-idx="${start + i}">
              <td><input type="number" class="note-pitch" value="${n.pitch_midi}" min="0" max="127" step="1" style="width:60px" /></td>
              <td><input type="number" class="note-start" value="${n.start_sec.toFixed(3)}" min="0" step="0.01" style="width:80px" /></td>
              <td><input type="number" class="note-end" value="${n.end_sec.toFixed(3)}" min="0" step="0.01" style="width:80px" /></td>
              <td>${n.velocity}</td>
              <td><button class="note-update-btn" data-note-id="${n.id}" data-idx="${start + i}">Update</button></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      ${totalPages > 1 ? `
        <div style="display:flex; gap:0.5rem; margin-top:0.5rem; align-items:center;">
          <button id="note-prev" ${notePage === 0 ? "disabled" : ""}>Prev</button>
          <span>Page ${notePage + 1} / ${totalPages} (${allNotes.length} notes)</span>
          <button id="note-next" ${notePage >= totalPages - 1 ? "disabled" : ""}>Next</button>
        </div>
      ` : `<p>${allNotes.length} notes total.</p>`}
    `;

    noteList.querySelector("#note-prev")?.addEventListener("click", () => {
      notePage = Math.max(0, notePage - 1);
      renderNoteList();
    });
    noteList.querySelector("#note-next")?.addEventListener("click", () => {
      notePage = Math.min(totalPages - 1, notePage + 1);
      renderNoteList();
    });

    noteList.querySelectorAll<HTMLButtonElement>(".note-update-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const idx = parseInt(btn.dataset.idx!);
        const note = allNotes[idx];
        const row = btn.closest("tr")!;
        const pitch = parseInt((row.querySelector(".note-pitch") as HTMLInputElement).value);
        const startSec = parseFloat((row.querySelector(".note-start") as HTMLInputElement).value);
        const endSec = parseFloat((row.querySelector(".note-end") as HTMLInputElement).value);

        if (endSec <= startSec) {
          statusBar.textContent = "Error: end must be after start.";
          return;
        }
        if (pitch < 0 || pitch > 127) {
          statusBar.textContent = "Error: pitch must be 0–127.";
          return;
        }

        btn.disabled = true;
        try {
          const updated = await updateNote(trackId, note.id, {
            pitch_midi: pitch,
            start_sec: startSec,
            end_sec: endSec,
          });
          allNotes[idx] = { ...note, ...updated };
          notesModified = true;
          pianoRoll?.setNotes(allNotes);
          statusBar.textContent = `Note updated (pitch=${updated.pitch_midi}).`;
          renderNoteList();
        } catch (e) {
          statusBar.textContent = `Update failed: ${e}`;
          btn.disabled = false;
        }
      });
    });
  }

  // Load existing notes if already extracted
  getNotes(trackId)
    .then((data) => {
      if (data.notes?.length) {
        allNotes = data.notes;
        renderNoteList();
        mountPianoRoll(allNotes);
      }
    })
    .catch(() => {});
}
