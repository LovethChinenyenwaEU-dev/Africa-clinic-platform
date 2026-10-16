import { beforeEach, describe, expect, it, vi } from "vitest";

import { getMessages, mergeMessages, openRoom, sendMessage, switchMode } from "./api";
import { shouldStepDown, suggestedMode } from "./connection";
import type { Message } from "./schemas";

const fetchMock = vi.fn();
const VISIT = "22222222-2222-4222-8222-222222222222";
const ROOM = {
  appointment_id: VISIT,
  provider: "jitsi",
  mode: "video",
  video_url: "https://meet.jit.si/clinic-abc#config.resolution=360",
  audio_url: "https://meet.jit.si/clinic-abc#config.startAudioOnly=true",
};

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function message(id: string, sentAt: string, body = "Hello"): Message {
  return { id, sender: "staff", sender_staff_id: null, body, sent_at: sentAt };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("stepping down on a weak connection (FR-C4)", () => {
  it.each([
    [{ effectiveType: "4g", downlink: 10 }, "video"],
    [{ effectiveType: "3g", downlink: 1.5 }, "video"],
    [{ effectiveType: "3g", downlink: 0.5 }, "audio"],
    [{ effectiveType: "2g" }, "audio"],
    [{ effectiveType: "4g", downlink: 5, saveData: true }, "audio"],
    [{ effectiveType: "slow-2g" }, "text"],
    [{ downlink: 0.1 }, "text"],
  ] as const)("%j suggests %s", (hint, mode) => {
    expect(suggestedMode(hint)).toBe(mode);
  });

  it("says nothing when the browser cannot tell", () => {
    expect(suggestedMode(null)).toBeNull();
    expect(suggestedMode({})).toBeNull();
  });

  it("only ever suggests stepping down, never up", () => {
    expect(shouldStepDown("video", "audio")).toBe(true);
    expect(shouldStepDown("audio", "text")).toBe(true);
    expect(shouldStepDown("text", "video")).toBe(false);
    expect(shouldStepDown("audio", "audio")).toBe(false);
    expect(shouldStepDown("video", null)).toBe(false);
  });
});

describe("the chat", () => {
  it("adds new messages once each, oldest first", () => {
    const known = [message("a", "2026-11-02T08:00:00Z"), message("b", "2026-11-02T08:01:00Z")];
    const fresh = [message("b", "2026-11-02T08:01:00Z"), message("c", "2026-11-02T08:02:00Z")];

    expect(mergeMessages(known, fresh).map((m) => m.id)).toEqual(["a", "b", "c"]);
  });

  it("asks only for messages since the newest one seen", async () => {
    fetchMock.mockResolvedValueOnce(answer([]));

    await getMessages(VISIT, "2026-11-02T08:01:00+00:00");

    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/backend/teleconsults/${VISIT}/messages?since=2026-11-02T08%3A01%3A00%2B00%3A00`,
    );
  });

  it("sends a message with an ID made on the device", async () => {
    fetchMock.mockResolvedValueOnce(
      answer(message("33333333-3333-4333-8333-333333333333", "2026-11-02T08:00:00Z"), 201),
    );

    await sendMessage(VISIT, "Can you hear me?");

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.body).toBe("Can you hear me?");
    expect(body.id).toMatch(/^[0-9a-f-]{36}$/);
  });
});

describe("the room", () => {
  it("opens the room and switches mode with a reason", async () => {
    fetchMock.mockResolvedValueOnce(answer(ROOM));
    fetchMock.mockResolvedValueOnce(answer({ ...ROOM, mode: "audio" }));

    await openRoom(VISIT);
    const switched = await switchMode(VISIT, "audio", "poor_connection");

    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/teleconsults/${VISIT}/room`);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      mode: "audio",
      reason: "poor_connection",
    });
    expect(switched.mode).toBe("audio");
  });
});
