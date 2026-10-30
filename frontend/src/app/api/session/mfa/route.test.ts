import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const { cookieStore } = vi.hoisted(() => ({
  cookieStore: { get: vi.fn(), set: vi.fn() },
}));
vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

import { POST } from "./route";

const fetchMock = vi.fn();

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function fakeRequest(body: unknown, origin: string | null = "http://localhost:3000"): Request {
  const headers = new Headers();
  if (origin) headers.set("origin", origin);
  headers.set("host", "localhost:3000");
  return { headers, json: () => Promise.resolve(body) } as unknown as Request;
}

function withChallenge(value: string | undefined = "challenge-abc") {
  cookieStore.get.mockImplementation((name: string) =>
    name === "clinic_mfa_challenge" && value ? { value } : undefined,
  );
}

function sentTo(call = 0) {
  const [url, init] = fetchMock.mock.calls[call];
  return { url: String(url), body: JSON.parse(init.body) };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  process.env.API_INTERNAL_URL = "http://backend.test";
});

describe("POST /api/session/mfa", () => {
  it("refuses other sites, and a missing or expired challenge, without asking the backend", async () => {
    withChallenge();
    const foreign = await POST(fakeRequest({ step: "setup" }, "https://evil.example"));
    withChallenge(undefined);
    const expired = await POST(fakeRequest({ step: "verify", code: "123456" }));

    expect(foreign.status).toBe(403);
    expect(expired.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("passes the challenge from the cookie and returns the set-up key", async () => {
    withChallenge();
    fetchMock.mockResolvedValueOnce(answer({ secret: "ABCDEFGH", otpauth_uri: "otpauth://x" }));

    const response = await POST(fakeRequest({ step: "setup" }));

    expect(await response.json()).toEqual({ secret: "ABCDEFGH", otpauth_uri: "otpauth://x" });
    expect(sentTo()).toEqual({
      url: "http://backend.test/api/v1/auth/mfa/setup",
      body: { challenge_token: "challenge-abc" },
    });
  });

  it("signs in after the code: session cookie set, challenge cleared, token never returned", async () => {
    withChallenge();
    fetchMock.mockResolvedValueOnce(answer({ access_token: "tok-9", token_type: "bearer" }));

    const response = await POST(fakeRequest({ step: "verify", code: " 123 456 " }));

    const text = await response.text();
    expect(response.status).toBe(200);
    expect(text).not.toContain("tok-9");
    expect(sentTo().body).toEqual({ challenge_token: "challenge-abc", code: "123 456" });
    expect(cookieStore.set).toHaveBeenCalledWith(
      expect.objectContaining({ name: "clinic_session", value: "tok-9", httpOnly: true }),
    );
    expect(cookieStore.set).toHaveBeenCalledWith(
      expect.objectContaining({ name: "clinic_mfa_challenge", value: "", maxAge: 0 }),
    );
  });

  it("hands the backup codes to the page once, after the first code", async () => {
    withChallenge();
    fetchMock.mockResolvedValueOnce(
      answer({ access_token: "tok-1", token_type: "bearer", backup_codes: ["ABCD-EFGH"] }),
    );

    const response = await POST(fakeRequest({ step: "confirm", code: "654321" }));

    expect(await response.json()).toEqual({ ok: true, backup_codes: ["ABCD-EFGH"] });
  });

  it.each([
    [401, 401],
    [429, 429],
    [409, 409],
    [500, 502],
  ])("turns a backend %s into %s and signs nobody in", async (backend, ours) => {
    withChallenge();
    fetchMock.mockResolvedValueOnce(answer({ detail: "no" }, backend));

    const response = await POST(fakeRequest({ step: "verify", code: "123456" }));

    expect(response.status).toBe(ours);
    expect(cookieStore.set).not.toHaveBeenCalled();
  });

  it("refuses a code that is too short without asking the backend", async () => {
    withChallenge();

    const response = await POST(fakeRequest({ step: "verify", code: "12" }));

    expect(response.status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
