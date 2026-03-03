import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  uploadTrack,
  recordTrack,
  extractMidi,
  getNotes,
  updateNote,
  synthesize,
  playbackUrl,
  getWaveform,
} from "./api";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("api client", () => {
  describe("uploadTrack", () => {
    it("sends POST with FormData and returns TrackInfo", async () => {
      const trackInfo = { track_id: "abc", duration_sec: 3.2, sample_rate: 22050 };
      mockFetch.mockResolvedValue(jsonResponse(trackInfo));

      const file = new File(["audio"], "test.wav", { type: "audio/wav" });
      const result = await uploadTrack(file);

      expect(mockFetch).toHaveBeenCalledOnce();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe("/audio/upload");
      expect(opts.method).toBe("POST");
      expect(opts.body).toBeInstanceOf(FormData);
      expect(result).toEqual(trackInfo);
    });

    it("throws on non-ok response", async () => {
      mockFetch.mockResolvedValue(jsonResponse({ detail: "Bad format" }, 400));
      const file = new File(["audio"], "test.txt");
      await expect(uploadTrack(file)).rejects.toThrow("Bad format");
    });
  });

  describe("recordTrack", () => {
    it("sends POST with blob and filename", async () => {
      const trackInfo = { track_id: "rec1", duration_sec: 5.0, sample_rate: 22050 };
      mockFetch.mockResolvedValue(jsonResponse(trackInfo));

      const blob = new Blob(["data"], { type: "audio/wav" });
      const result = await recordTrack(blob, "my-recording.wav");

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe("/audio/record");
      expect(opts.method).toBe("POST");
      expect(result.track_id).toBe("rec1");
    });
  });

  describe("extractMidi", () => {
    it("sends POST to correct endpoint", async () => {
      const notes = { notes: [{ id: "n1", pitch_midi: 60, start_sec: 0, end_sec: 1, velocity: 80 }] };
      mockFetch.mockResolvedValue(jsonResponse(notes));

      const result = await extractMidi("track-123");
      expect(mockFetch.mock.calls[0][0]).toBe("/midi/track-123/extract");
      expect(result.notes).toHaveLength(1);
    });
  });

  describe("getNotes", () => {
    it("fetches notes for a track", async () => {
      mockFetch.mockResolvedValue(jsonResponse({ notes: [] }));
      const result = await getNotes("track-1");
      expect(mockFetch.mock.calls[0][0]).toBe("/midi/track-1");
      expect(result.notes).toEqual([]);
    });
  });

  describe("updateNote", () => {
    it("sends PUT with JSON body", async () => {
      const updated = { id: "n1", track_id: "t1", pitch_midi: 62, start_sec: 0, end_sec: 1, velocity: 80 };
      mockFetch.mockResolvedValue(jsonResponse(updated));

      await updateNote("t1", "n1", { pitch_midi: 62 });
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe("/midi/t1/notes/n1");
      expect(opts.method).toBe("PUT");
      expect(JSON.parse(opts.body)).toEqual({ pitch_midi: 62 });
    });
  });

  describe("synthesize", () => {
    it("sends POST and returns playback_url", async () => {
      mockFetch.mockResolvedValue(jsonResponse({ playback_url: "/audio/t1/playback" }));
      const result = await synthesize("t1");
      expect(result.playback_url).toBe("/audio/t1/playback");
    });
  });

  describe("playbackUrl", () => {
    it("returns correct path", () => {
      expect(playbackUrl("abc-123")).toBe("/audio/abc-123/playback");
    });
  });

  describe("getWaveform", () => {
    it("fetches waveform data", async () => {
      const data = { times: [0, 0.1], amplitudes: [0.5, 0.3] };
      mockFetch.mockResolvedValue(jsonResponse(data));
      const result = await getWaveform("t1");
      expect(result.times).toEqual([0, 0.1]);
    });
  });

  describe("error handling", () => {
    it("falls back to statusText when response is not JSON", async () => {
      mockFetch.mockResolvedValue(new Response("not json", { status: 500, statusText: "Internal Server Error" }));
      await expect(uploadTrack(new File(["x"], "x.wav"))).rejects.toThrow("Internal Server Error");
    });
  });
});
