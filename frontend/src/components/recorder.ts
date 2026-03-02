import { recordTrack } from "../api";
import { getState, setState } from "../state";

export function renderRecorder(container: HTMLElement) {
  container.innerHTML = `
    <div class="card">
      <h2>Record from Microphone</h2>
      <p>Click Record to start, Stop when done.</p>
      <button id="rec-start">Record</button>
      <button id="rec-stop" disabled>Stop</button>
      <audio id="rec-preview" controls class="hidden"></audio>
      <button id="rec-process" class="hidden">Process Recording</button>
      <p id="rec-status"></p>
    </div>
  `;

  const startBtn = document.getElementById("rec-start") as HTMLButtonElement;
  const stopBtn = document.getElementById("rec-stop") as HTMLButtonElement;
  const preview = document.getElementById("rec-preview") as HTMLAudioElement;
  const processBtn = document.getElementById("rec-process") as HTMLButtonElement;
  const status = document.getElementById("rec-status")!;

  let mediaRecorder: MediaRecorder | null = null;
  let chunks: Blob[] = [];
  let previewUrl: string | null = null;

  startBtn.addEventListener("click", async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      chunks = [];
      mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/wav" });
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(blob);
        preview.src = previewUrl;
        preview.classList.remove("hidden");
        processBtn.classList.remove("hidden");
        processBtn.onclick = async () => {
          processBtn.disabled = true;
          status.textContent = "Processing...";
          try {
            const result = await recordTrack(blob);
            const tracks = [...getState().tracks, {
              track_id: result.track_id,
              filename: "recording.wav",
              duration_sec: result.duration_sec,
            }];
            setState({ tracks, activeTrackId: result.track_id });
            status.textContent = `Recorded — ${result.duration_sec.toFixed(1)}s. Go to Editor tab.`;
          } catch (e) {
            status.textContent = `Error: ${e}`;
          }
          processBtn.disabled = false;
        };
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorder.start();
      startBtn.disabled = true;
      stopBtn.disabled = false;
      status.textContent = "Recording...";
    } catch (e) {
      status.textContent = `Mic access denied: ${e}`;
    }
  });

  stopBtn.addEventListener("click", () => {
    mediaRecorder?.stop();
    startBtn.disabled = false;
    stopBtn.disabled = true;
    status.textContent = "Recording stopped. Preview below.";
  });
}
