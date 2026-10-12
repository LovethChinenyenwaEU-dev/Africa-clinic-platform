import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const { cookieStore } = vi.hoisted(() => ({
  cookieStore: { get: vi.fn(), set: vi.fn() },
}));
vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

import { getCurrentUser } from "./current-user";

const fetchMock = vi.fn();

const ME = {
  id: "11111111-1111-4111-8111-111111111111",
  tenant_id: "22222222-2222-4222-8222-222222222222",
  email: "nurse@example.com",
  full_name: "Test Nurse",
  role: "nurse",
};

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  process.env.API_INTERNAL_URL = "http://backend.test";
});

describe("getCurrentUser", () => {
  it("returns null without calling the backend when there is no cookie", async () => {
    cookieStore.get.mockReturnValue(undefined);

    expect(await getCurrentUser()).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns the person the backend recognises", async () => {
    cookieStore.get.mockReturnValue({ value: "tok-123" });
    fetchMock.mockResolvedValueOnce(answer(ME));

    expect(await getCurrentUser()).toEqual(ME);
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer tok-123");
  });

  it("returns null when the backend no longer accepts the session", async () => {
    cookieStore.get.mockReturnValue({ value: "tok-123" });
    fetchMock.mockResolvedValueOnce(answer({ detail: "Not authenticated." }, 401));

    expect(await getCurrentUser()).toBeNull();
  });

  it("does not mistake a backend outage for being signed out", async () => {
    cookieStore.get.mockReturnValue({ value: "tok-123" });
    fetchMock.mockRejectedValueOnce(new Error("connection refused"));

    await expect(getCurrentUser()).rejects.toThrow();
  });
});