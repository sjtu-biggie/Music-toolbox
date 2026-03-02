import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderRecorder } from "./recorder";

vi.mock("../api", () => ({
  recordTrack: vi.fn(),
}));

vi.mock("../state", () => ({
  getState: vi.fn(() => ({ tracks: [], activeTrackId: null })),
  setState: vi.fn(),
}));

let container: HTMLDivElement;

beforeEach(() => {
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  document.body.removeChild(container);
});

describe("renderRecorder", () => {
  it("renders record and stop buttons", () => {
    renderRecorder(container);

    expect(container.querySelector("#rec-start")).toBeTruthy();
    expect(container.querySelector("#rec-stop")).toBeTruthy();
    expect(container.textContent).toContain("Record from Microphone");
  });

  it("stop button is initially disabled", () => {
    renderRecorder(container);
    const stopBtn = container.querySelector("#rec-stop") as HTMLButtonElement;
    expect(stopBtn.disabled).toBe(true);
  });

  it("record button is initially enabled", () => {
    renderRecorder(container);
    const startBtn = container.querySelector("#rec-start") as HTMLButtonElement;
    expect(startBtn.disabled).toBe(false);
  });

  it("shows error when mic access denied", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error("Permission denied")) },
      configurable: true,
    });

    renderRecorder(container);

    const startBtn = container.querySelector("#rec-start") as HTMLButtonElement;
    startBtn.click();

    await vi.waitFor(() => {
      const status = container.querySelector("#rec-status");
      expect(status?.textContent).toContain("Mic access denied");
    });
  });

  it("preview and process button are hidden initially", () => {
    renderRecorder(container);

    const preview = container.querySelector("#rec-preview") as HTMLElement;
    const processBtn = container.querySelector("#rec-process") as HTMLElement;
    expect(preview.classList.contains("hidden")).toBe(true);
    expect(processBtn.classList.contains("hidden")).toBe(true);
  });
});
