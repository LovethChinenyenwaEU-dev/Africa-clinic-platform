import { beforeEach, describe, expect, it, vi } from "vitest";

import { endMyDevice, getMyDevices, sortDevices, type Device } from "./devices";

const fetchMock = vi.fn();

function device(id: string, lastSeen: string, current = false): Device {
  return {
    id,
    label: "Chrome on Windows",
    created_at: "2026-10-30T08:00:00Z",
    last_seen_at: lastSeen,
    current,
  };
}

const A = "0b7c6f1e-2d3a-4c5b-8e9f-1a2b3c4d5e6f";
const B = "1b7c6f1e-2d3a-4c5b-8e9f-1a2b3c4d5e6f";
const C = "2b7c6f1e-2d3a-4c5b-8e9f-1a2b3c4d5e6f";

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("my devices", () => {
  it("puts this device first, then the most recently used", () => {
    const sorted = sortDevices([
      device(A, "2026-10-30T09:00:00Z"),
      device(B, "2026-10-30T08:00:00Z", true),
      device(C, "2026-10-30T10:00:00Z"),
    ]);

    expect(sorted.map((d) => d.id)).toEqual([B, C, A]);
  });

  it("reads the list through the staff pass-through", async () => {
    fetchMock.mockResolvedValueOnce(answer([device(A, "2026-10-30T09:00:00Z", true)]));

    const devices = await getMyDevices();

    expect(devices).toHaveLength(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/backend/staff/me/sessions");
  });

  it("ends one device with a POST", async () => {
    fetchMock.mockResolvedValueOnce(answer({ signed_out: true }));

    await endMyDevice(A);

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain(`/api/backend/staff/me/sessions/${A}/end`);
    expect(init.method).toBe("POST");
  });
});
