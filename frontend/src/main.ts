import { renderUpload } from "./components/upload";
import { renderRecorder } from "./components/recorder";

const app = document.getElementById("app")!;

type View = "upload" | "record" | "editor";
let currentView: View = "upload";

function render() {
  app.innerHTML = `
    <h1>AI Music</h1>
    <div class="tab-bar">
      <button data-view="upload" class="${currentView === "upload" ? "active" : ""}">Upload</button>
      <button data-view="record" class="${currentView === "record" ? "active" : ""}">Record</button>
      <button data-view="editor" class="${currentView === "editor" ? "active" : ""}">Editor</button>
    </div>
    <div id="view-container"></div>
  `;

  app.querySelectorAll<HTMLButtonElement>(".tab-bar button").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentView = btn.dataset.view as View;
      render();
    });
  });

  const container = document.getElementById("view-container")!;
  switch (currentView) {
    case "upload":
      renderUpload(container);
      break;
    case "record":
      renderRecorder(container);
      break;
    case "editor":
      renderEditor(container);
      break;
  }
}

function renderEditor(container: HTMLElement) {
  import("./components/waveform").then(({ renderEditorView }) => {
    renderEditorView(container);
  });
}

render();
