import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderUpload } from "./upload";

vi.mock("../api", () => ({
  uploadTrack: vi.fn(),
}));

vi.mock("../state", () => ({
  getState: vi.fn(() => ({ tracks: [], activeTrackId: null })),
  setState: vi.fn(),
}));

import { uploadTrack } from "../api";
import { getState, setState } from "../state";

const mockUpload = vi.mocked(uploadTrack);
const mockGetState = vi.mocked(getState);
const mockSetState = vi.mocked(setState);

let container: HTMLDivElement;

beforeEach(() => {
  vi.clearAllMocks();
  mockGetState.mockReturnValue({ tracks: [], activeTrackId: null });
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  document.body.removeChild(container);
});

describe("renderUpload", () => {
  it("renders upload form and empty track list", () => {
    renderUpload(container);

    expect(container.querySelector("#file-input")).toBeTruthy();
    expect(container.querySelector("#upload-btn")).toBeTruthy();
    expect(container.textContent).toContain("No tracks yet");
  });

  it("disables upload button when no file selected", () => {
    renderUpload(container);
    const btn = container.querySelector("#upload-btn") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("renders existing tracks from state", () => {
    mockGetState.mockReturnValue({
      tracks: [
        { track_id: "t1", filename: "song.mp3", duration_sec: 4.5 },
        { track_id: "t2", filename: "voice.wav", duration_sec: 2.1 },
      ],
      activeTrackId: "t1",
    });

    renderUpload(container);

    const buttons = container.querySelectorAll(".track-select");
    expect(buttons).toHaveLength(2);
    expect(buttons[0].textContent).toContain("song.mp3");
    expect(buttons[1].textContent).toContain("voice.wav");
  });

  it("calls uploadTrack on button click and updates state", async () => {
    mockUpload.mockResolvedValue({ track_id: "new-t", duration_sec: 3.0, sample_rate: 22050 });

    renderUpload(container);

    const fileInput = container.querySelector("#file-input") as HTMLInputElement;
    const uploadBtn = container.querySelector("#upload-btn") as HTMLButtonElement;

    // Simulate file selection
    const file = new File(["audio"], "test.wav", { type: "audio/wav" });
    Object.defineProperty(fileInput, "files", { value: [file], writable: false });
    fileInput.dispatchEvent(new Event("change"));
    expect(uploadBtn.disabled).toBe(false);

    // Click upload
    uploadBtn.click();
    await vi.waitFor(() => expect(mockUpload).toHaveBeenCalledWith(file));
    await vi.waitFor(() => expect(mockSetState).toHaveBeenCalled());

    const call = mockSetState.mock.calls[0][0];
    expect(call.tracks).toHaveLength(1);
    expect(call.activeTrackId).toBe("new-t");
  });

  it("sets active track when track button clicked", () => {
    mockGetState.mockReturnValue({
      tracks: [{ track_id: "t1", filename: "a.wav", duration_sec: 1 }],
      activeTrackId: null,
    });

    renderUpload(container);

    const trackBtn = container.querySelector(".track-select") as HTMLButtonElement;
    trackBtn.click();
    expect(mockSetState).toHaveBeenCalledWith({ activeTrackId: "t1" });
  });

  it("shows error message on upload failure", async () => {
    mockUpload.mockRejectedValue(new Error("Upload failed"));

    renderUpload(container);

    const fileInput = container.querySelector("#file-input") as HTMLInputElement;
    const uploadBtn = container.querySelector("#upload-btn") as HTMLButtonElement;

    Object.defineProperty(fileInput, "files", { value: [new File(["x"], "x.wav")], writable: false });
    fileInput.dispatchEvent(new Event("change"));
    uploadBtn.click();

    await vi.waitFor(() => {
      const status = container.querySelector("#upload-status");
      expect(status?.textContent).toContain("Error");
    });
  });
});
