import { uploadTrack } from "../api";
import { getState, setState } from "../state";

export function renderUpload(container: HTMLElement) {
  const state = getState();

  container.innerHTML = `
    <div class="card">
      <h2>Upload Audio</h2>
      <p>Supported: mp3, wav, m4a, flac, ogg</p>
      <input type="file" id="file-input" accept=".mp3,.wav,.m4a,.flac,.ogg" />
      <button id="upload-btn" disabled>Upload</button>
      <p id="upload-status"></p>
    </div>
    <div class="card">
      <h2>Tracks</h2>
      <ul id="track-list">
        ${state.tracks.length === 0
          ? "<li>No tracks yet</li>"
          : state.tracks
              .map(
                (t) =>
                  `<li>
                    <button class="track-select" data-id="${t.track_id}">
                      ${t.filename} (${t.duration_sec.toFixed(1)}s)
                    </button>
                  </li>`
              )
              .join("")}
      </ul>
    </div>
  `;

  const fileInput = document.getElementById("file-input") as HTMLInputElement;
  const uploadBtn = document.getElementById("upload-btn") as HTMLButtonElement;
  const status = document.getElementById("upload-status")!;

  fileInput.addEventListener("change", () => {
    uploadBtn.disabled = !fileInput.files?.length;
  });

  uploadBtn.addEventListener("click", async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    uploadBtn.disabled = true;
    status.textContent = "Uploading...";
    try {
      const result = await uploadTrack(file);
      const tracks = [...getState().tracks, {
        track_id: result.track_id,
        filename: file.name,
        duration_sec: result.duration_sec,
      }];
      setState({ tracks, activeTrackId: result.track_id });
      status.textContent = `Uploaded — ${result.duration_sec.toFixed(1)}s. Go to Editor tab.`;
    } catch (e) {
      status.textContent = `Error: ${e}`;
    }
    uploadBtn.disabled = false;
  });

  container.querySelectorAll<HTMLButtonElement>(".track-select").forEach((btn) => {
    btn.addEventListener("click", () => {
      setState({ activeTrackId: btn.dataset.id! });
    });
  });
}
