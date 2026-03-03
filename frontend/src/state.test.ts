import { describe, it, expect, vi, beforeEach } from "vitest";

// Fresh module for each test to avoid shared state
let getState: typeof import("./state").getState;
let setState: typeof import("./state").setState;
let subscribe: typeof import("./state").subscribe;

beforeEach(async () => {
  vi.resetModules();
  const mod = await import("./state");
  getState = mod.getState;
  setState = mod.setState;
  subscribe = mod.subscribe;
});

describe("state", () => {
  it("starts with empty tracks and no active track", () => {
    const s = getState();
    expect(s.tracks).toEqual([]);
    expect(s.activeTrackId).toBeNull();
  });

  it("updates state with setState", () => {
    setState({ activeTrackId: "t1" });
    expect(getState().activeTrackId).toBe("t1");
  });

  it("merges partial updates", () => {
    setState({ tracks: [{ track_id: "t1", filename: "a.wav", duration_sec: 3 }] });
    setState({ activeTrackId: "t1" });
    expect(getState().tracks).toHaveLength(1);
    expect(getState().activeTrackId).toBe("t1");
  });

  it("notifies subscribers on state change", () => {
    const listener = vi.fn();
    subscribe(listener);
    setState({ activeTrackId: "t2" });
    expect(listener).toHaveBeenCalledOnce();
  });

  it("unsubscribes correctly", () => {
    const listener = vi.fn();
    const unsub = subscribe(listener);
    unsub();
    setState({ activeTrackId: "t3" });
    expect(listener).not.toHaveBeenCalled();
  });

  it("notifies multiple subscribers", () => {
    const a = vi.fn();
    const b = vi.fn();
    subscribe(a);
    subscribe(b);
    setState({ activeTrackId: "t4" });
    expect(a).toHaveBeenCalledOnce();
    expect(b).toHaveBeenCalledOnce();
  });
});
