import WaveSurfer from "wavesurfer.js";
import { requestAIModify, pollJob, aiResultUrl, spliceAIResult, regionUrl } from "../api";
import { getState, setState } from "../state";

export interface AIPanelOptions {
  trackId: string;
  getRegion: () => { startSec: number; endSec: number } | null;
  onTrackCreated: (splicedTrackId: string) => void;
}

export function renderAIPanel(container: HTMLElement, options: AIPanelOptions) {
  const { trackId, getRegion, onTrackCreated } = options;

  container.innerHTML = `
    <div class="card ai-panel">
      <h3>AI Modify</h3>

      <div style="margin-bottom: 0.75rem;">
        <label>Mode:</label>
        <div class="ai-mode-buttons" style="display:flex; gap:0.5rem; margin-top:0.25rem;">
          <button class="ai-mode active" data-mode="style">Style Transfer</button>
          <button class="ai-mode" data-mode="melody">Melody Variation</button>
          <button class="ai-mode" data-mode="accompaniment">Accompaniment</button>
        </div>
      </div>

      <div style="margin-bottom: 0.75rem;">
        <label>Provider:</label>
        <div style="display:flex; gap:1rem; margin-top:0.25rem;">
          <label><input type="radio" name="ai-provider" value="local" checked /> Local GPU</label>
          <label><input type="radio" name="ai-provider" value="replicate" /> Cloud (Replicate)</label>
        </div>
      </div>

      <div id="ai-region-display" style="margin-bottom: 0.75rem; font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-secondary);">
        No region selected — drag on waveform or piano roll first.
      </div>

      <div style="margin-bottom: 0.75rem;">
        <textarea id="ai-prompt" rows="2" placeholder="Describe the style you want, e.g. 'jazz saxophone', 'upbeat electronic'..."
          style="width:100%; background:var(--bg-primary); color:var(--text-primary); border:1px solid var(--border); border-radius:4px; padding:0.5rem; font-size:0.9rem; resize:vertical;"></textarea>
      </div>

      <button id="ai-generate" style="width:100%; margin-bottom:0.75rem;">Generate</button>

      <div id="ai-status" style="font-family: var(--font-mono); font-size: 0.85rem; margin-bottom: 0.75rem;"></div>

      <div id="ai-result" class="hidden">
        <h4>Compare</h4>
        <div style="display:flex; gap:1rem; margin-bottom:0.75rem;">
          <div style="flex:1;">
            <p style="font-size:0.85rem; color:var(--text-secondary);">Original</p>
            <div id="ai-waveform-original"></div>
          </div>
          <div style="flex:1;">
            <p style="font-size:0.85rem; color:var(--text-secondary);">AI Modified</p>
            <div id="ai-waveform-modified"></div>
          </div>
        </div>
        <button id="ai-apply" style="width:100%;">Apply to Track</button>
      </div>
    </div>
  `;

  let selectedMode: "style" | "melody" | "accompaniment" = "style";
  let currentJobId: string | null = null;
  let pollTimer: number | null = null;

  // Mode buttons
  container.querySelectorAll<HTMLButtonElement>(".ai-mode").forEach((btn) => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".ai-mode").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedMode = btn.dataset.mode as typeof selectedMode;
    });
  });

  // Update region display
  function updateRegionDisplay() {
    const region = getRegion();
    const display = document.getElementById("ai-region-display")!;
    if (region) {
      display.textContent = `Selected: ${region.startSec.toFixed(2)}s — ${region.endSec.toFixed(2)}s`;
    } else {
      display.textContent = "No region selected — drag on waveform or piano roll first.";
    }
  }

  const regionCheckTimer = setInterval(updateRegionDisplay, 500);

  // Generate button
  document.getElementById("ai-generate")!.addEventListener("click", async () => {
    const region = getRegion();
    if (!region) {
      document.getElementById("ai-status")!.textContent = "Select a region first.";
      return;
    }

    const prompt = (document.getElementById("ai-prompt") as HTMLTextAreaElement).value.trim();
    if (!prompt) {
      document.getElementById("ai-status")!.textContent = "Enter a prompt.";
      return;
    }

    const provider = (container.querySelector<HTMLInputElement>("input[name='ai-provider']:checked"))!.value as "local" | "replicate";
    const statusEl = document.getElementById("ai-status")!;
    const generateBtn = document.getElementById("ai-generate") as HTMLButtonElement;

    generateBtn.disabled = true;
    statusEl.textContent = "Submitting job...";

    try {
      const { job_id } = await requestAIModify(trackId, selectedMode, prompt, region.startSec, region.endSec, provider);
      currentJobId = job_id;
      statusEl.textContent = `Job ${job_id.slice(0, 8)}... submitted. Polling...`;

      pollTimer = window.setInterval(async () => {
        try {
          const job = await pollJob(job_id);
          statusEl.textContent = `Job status: ${job.status}`;

          if (job.status === "done") {
            clearInterval(pollTimer!);
            pollTimer = null;
            generateBtn.disabled = false;
            statusEl.textContent = "Generation complete!";
            showResult(region);
          } else if (job.status === "failed") {
            clearInterval(pollTimer!);
            pollTimer = null;
            generateBtn.disabled = false;
            statusEl.textContent = `Failed: ${job.error_msg || "unknown error"}`;
          }
        } catch (err) {
          statusEl.textContent = `Poll error: ${err}`;
        }
      }, 2000);
    } catch (err) {
      statusEl.textContent = `Error: ${err}`;
      generateBtn.disabled = false;
    }
  });

  function showResult(region: { startSec: number; endSec: number }) {
    const resultDiv = document.getElementById("ai-result")!;
    resultDiv.classList.remove("hidden");

    const origContainer = document.getElementById("ai-waveform-original")!;
    origContainer.innerHTML = "";
    WaveSurfer.create({
      container: origContainer,
      waveColor: "#4a4a6a",
      progressColor: "#4caf50",
      height: 48,
      url: regionUrl(trackId, region.startSec, region.endSec),
    });

    const modContainer = document.getElementById("ai-waveform-modified")!;
    modContainer.innerHTML = "";
    WaveSurfer.create({
      container: modContainer,
      waveColor: "#4a4a6a",
      progressColor: "#e94560",
      height: 48,
      url: aiResultUrl(currentJobId!),
    });
  }

  // Apply to Track
  document.getElementById("ai-apply")!.addEventListener("click", async () => {
    if (!currentJobId) return;
    const statusEl = document.getElementById("ai-status")!;
    const applyBtn = document.getElementById("ai-apply") as HTMLButtonElement;

    applyBtn.disabled = true;
    statusEl.textContent = "Splicing into full track...";

    try {
      const { spliced_track_id } = await spliceAIResult(trackId, currentJobId);
      statusEl.textContent = `Applied! New track: ${spliced_track_id.slice(0, 8)}...`;

      const state = getState();
      const spliceName = `AI splice of ${spliced_track_id.slice(0, 8)}`;
      const tracks = [...state.tracks, {
        track_id: spliced_track_id,
        name: spliceName,
        filename: `${spliced_track_id}.wav`,
        duration_sec: 0,
      }];
      setState({ tracks, activeTrackId: spliced_track_id });
      onTrackCreated(spliced_track_id);
    } catch (err) {
      statusEl.textContent = `Splice failed: ${err}`;
    }
    applyBtn.disabled = false;
  });

  return () => {
    if (pollTimer) clearInterval(pollTimer);
    clearInterval(regionCheckTimer);
  };
}
