import { describe, it, expect, vi } from "vitest";
import { renderToolbar } from "./toolbar";


describe("renderToolbar", () => {
  function setup() {
    const container = document.createElement("div");
    const callbacks = {
      onPlay: vi.fn(),
      onPause: vi.fn(),
      onStop: vi.fn(),
      onExtract: vi.fn(),
      onSynthesize: vi.fn(),
      onPlayRegion: vi.fn(),
      onSourceChange: vi.fn(),
      onInstrumentChange: vi.fn(),
      onTrackChange: vi.fn(),
    };
    const options = {
      tracks: [{ track_id: "t1", name: "Test Track" }],
      activeTrackId: "t1",
      instruments: ["piano", "violin"],
      defaultInstrument: "piano",
    };
    const controls = renderToolbar(container, options, callbacks);
    return { container, callbacks, controls };
  }

  it("renders all transport and action buttons", () => {
    const { container } = setup();
    expect(container.querySelector("#tb-play")).toBeTruthy();
    expect(container.querySelector("#tb-pause")).toBeTruthy();
    expect(container.querySelector("#tb-stop")).toBeTruthy();
    expect(container.querySelector("#tb-extract")).toBeTruthy();
    expect(container.querySelector("#tb-synth")).toBeTruthy();
    expect(container.querySelector("#tb-region")).toBeTruthy();
  });

  it("renders source toggle with original checked", () => {
    const { container } = setup();
    const original = container.querySelector("#src-original") as HTMLInputElement;
    const synth = container.querySelector("#src-synth") as HTMLInputElement;
    expect(original.checked).toBe(true);
    expect(synth.disabled).toBe(true);
  });

  it("calls onPlay when play clicked", () => {
    const { container, callbacks } = setup();
    (container.querySelector("#tb-play") as HTMLElement).click();
    expect(callbacks.onPlay).toHaveBeenCalledOnce();
  });

  it("calls onPause when pause clicked", () => {
    const { container, callbacks } = setup();
    (container.querySelector("#tb-pause") as HTMLElement).click();
    expect(callbacks.onPause).toHaveBeenCalledOnce();
  });

  it("calls onStop when stop clicked", () => {
    const { container, callbacks } = setup();
    (container.querySelector("#tb-stop") as HTMLElement).click();
    expect(callbacks.onStop).toHaveBeenCalledOnce();
  });

  it("calls onExtract when extract clicked", () => {
    const { container, callbacks } = setup();
    (container.querySelector("#tb-extract") as HTMLElement).click();
    expect(callbacks.onExtract).toHaveBeenCalledOnce();
  });

  it("calls onSynthesize when synth clicked", () => {
    const { container, callbacks } = setup();
    (container.querySelector("#tb-synth") as HTMLElement).click();
    expect(callbacks.onSynthesize).toHaveBeenCalledOnce();
  });

  it("setSynthEnabled enables synth radio", () => {
    const { container, controls } = setup();
    const synth = container.querySelector("#src-synth") as HTMLInputElement;
    expect(synth.disabled).toBe(true);
    controls.setSynthEnabled(true);
    expect(synth.disabled).toBe(false);
  });

  it("setSource switches active radio", () => {
    const { controls } = setup();
    controls.setSynthEnabled(true);
    controls.setSource("synth");
    expect(controls.getSource()).toBe("synth");
  });

  it("renders control-bar container", () => {
    const { container } = setup();
    expect(container.querySelector(".control-bar")).toBeTruthy();
  });
});
