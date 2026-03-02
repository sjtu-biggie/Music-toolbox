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
    };
    renderToolbar(container, callbacks);
    return { container, callbacks };
  }

  it("renders all transport buttons", () => {
    const { container } = setup();
    expect(container.querySelector("#tb-play")).toBeTruthy();
    expect(container.querySelector("#tb-pause")).toBeTruthy();
    expect(container.querySelector("#tb-stop")).toBeTruthy();
    expect(container.querySelector("#tb-extract")).toBeTruthy();
    expect(container.querySelector("#tb-synth")).toBeTruthy();
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

  it("appends toolbar as child of container", () => {
    const { container } = setup();
    expect(container.children).toHaveLength(1);
    expect(container.children[0].classList.contains("toolbar")).toBe(true);
  });
});
