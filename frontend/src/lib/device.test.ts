import { afterEach, describe, expect, it, vi } from "vitest";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function fakeStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    data,
  };
}

async function freshModule() {
  vi.resetModules();
  return import("./device");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getDeviceId", () => {
  it("makes an ID once and keeps it on the device", async () => {
    const store = fakeStorage();
    vi.stubGlobal("window", { localStorage: store });
    const { getDeviceId } = await freshModule();

    const first = getDeviceId();

    expect(first).toMatch(UUID);
    expect(getDeviceId()).toBe(first);
    expect(store.data.get("clinic.device-id")).toBe(first);
  });

  it("reuses the ID already saved on the device", async () => {
    const saved = "11111111-2222-4333-8444-555555555555";
    vi.stubGlobal("window", { localStorage: fakeStorage({ "clinic.device-id": saved }) });
    const { getDeviceId } = await freshModule();

    expect(getDeviceId()).toBe(saved);
  });

  it("replaces a saved value that is not a proper ID", async () => {
    const store = fakeStorage({ "clinic.device-id": "tampered" });
    vi.stubGlobal("window", { localStorage: store });
    const { getDeviceId } = await freshModule();

    expect(getDeviceId()).toMatch(UUID);
    expect(store.data.get("clinic.device-id")).not.toBe("tampered");
  });

  it("still works when storage is blocked, keeping one ID for this visit", async () => {
    vi.stubGlobal("window", {
      get localStorage() {
        throw new Error("blocked");
      },
    });
    const { getDeviceId } = await freshModule();

    const first = getDeviceId();

    expect(first).toMatch(UUID);
    expect(getDeviceId()).toBe(first);
  });
});
