import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const { cookieStore } = vi.hoisted(() => ({
  cookieStore: { get: vi.fn(), set: vi.fn() },
}));
vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

import { DELETE, GET, POST } from "./route";

const SITE = "http://localhost:3000";
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

// A small stand-in for a browser request, so each test controls the headers.
function fakeRequest(options: {
  body?: unknown;
  brokenJson?: boolean;
  origin?: string | null;
  host?: string;
  forwardedHost?: string;
} = {}): Request {
  const headers = new Headers();
  const origin = options.origin === undefined ? SITE : options.origin;
  if (origin) headers.set("origin", origin);
  headers.set("host", options.host ?? "localhost:3000");
  if (options.forwardedHost) headers.set("x-forwarded-host", options.forwardedHost);
  return {
    headers,
    json: () =>
      options.brokenJson ? Promise.reject(new Error("bad json")) : Promise.resolve(options.body),
  } as unknown as Request;
}

const GOOD_LOGIN = { email: "  nurse@example.com ", password: "a-long-enough-password" };

beforeEach(() => {
  vi.resetAllMocks();
  vi.unstubAllEnvs();
  vi.stubGlobal("fetch", fetchMock);
  process.env.API_INTERNAL_URL = "http://backend.test";
});

describe("POST /api/session (log in)", () => {
  it("refuses requests that do not come from our own site", async () => {
    const foreign = await POST(fakeRequest({ body: GOOD_LOGIN, origin: "https://evil.example" }));
    const missing = await POST(fakeRequest({ body: GOOD_LOGIN, origin: null }));

    expect(foreign.status).toBe(403);
    expect(missing.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(cookieStore.set).not.toHaveBeenCalled();
  });

  it("accepts our own site behind a forwarding proxy", async () => {
    fetchMock.mockResolvedValueOnce(answer({ access_token: "tok", token_type: "bearer" }));

    const response = await POST(
      fakeRequest({
        body: GOOD_LOGIN,
        origin: "https://my-app.example",
        host: "localhost:3000",
        forwardedHost: "my-app.example",
      }),
    );

    expect(response.status).toBe(200);
  });

  it("rejects a bad form without calling the backend", async () => {
    const empty = await POST(fakeRequest({ body: { email: "", password: "" } }));
    const broken = await POST(fakeRequest({ brokenJson: true }));

    expect(empty.status).toBe(422);
    expect(broken.status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("logs in: tidies the form, locks the token in a safe cookie and never returns it", async () => {
    fetchMock.mockResolvedValueOnce(answer({ access_token: "tok-123", token_type: "bearer" }));

    const response = await POST(fakeRequest({ body: GOOD_LOGIN }));

    expect(response.status).toBe(200);
    expect(await response.text()).not.toContain("tok-123");
    expect(response.headers.get("cache-control")).toBe("no-store");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/v1/auth/login");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      email: "nurse@example.com",
      password: "a-long-enough-password",
    });

    expect(cookieStore.set).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "clinic_session",
        value: "tok-123",
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        maxAge: 1800,
      }),
    );
  });

  it("marks the cookie Secure in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    fetchMock.mockResolvedValueOnce(answer({ access_token: "tok", token_type: "bearer" }));

    await POST(fakeRequest({ body: GOOD_LOGIN }));

    expect(cookieStore.set).toHaveBeenCalledWith(expect.objectContaining({ secure: true }));
  });

  it("answers a wrong password with the same vague message and sets no cookie", async () => {
    fetchMock.mockResolvedValueOnce(answer({ detail: "Invalid email or password." }, 401));

    const response = await POST(fakeRequest({ body: GOOD_LOGIN }));

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ message: "Invalid email or password." });
    expect(cookieStore.set).not.toHaveBeenCalled();
  });

  it("answers 502 when the backend is down or sends nonsense, with no cookie", async () => {
    fetchMock.mockRejectedValueOnce(new Error("connection refused"));
    const down = await POST(fakeRequest({ body: GOOD_LOGIN }));

    fetchMock.mockResolvedValueOnce(answer({ surprise: true }));
    const nonsense = await POST(fakeRequest({ body: GOOD_LOGIN }));

    expect(down.status).toBe(502);
    expect(nonsense.status).toBe(502);
    expect(cookieStore.set).not.toHaveBeenCalled();
  });

  it("keeps an admin's challenge in its own short cookie and tells the page only the step", async () => {
    fetchMock.mockResolvedValueOnce(
      answer({ mfa: "verify", challenge_token: "challenge-abc", token_type: "bearer" }),
    );

    const response = await POST(fakeRequest({ body: GOOD_LOGIN }));

    expect(response.status).toBe(200);
    const text = await response.text();
    expect(JSON.parse(text)).toEqual({ mfa: "verify" });
    expect(text).not.toContain("challenge-abc");
    expect(cookieStore.set).toHaveBeenCalledTimes(1);
    expect(cookieStore.set).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "clinic_mfa_challenge",
        value: "challenge-abc",
        httpOnly: true,
        maxAge: 300,
      }),
    );
  });
});

describe("GET /api/session (who am I?)", () => {
  it("answers 401 without calling the backend when there is no cookie", async () => {
    cookieStore.get.mockReturnValue(undefined);

    const response = await GET();

    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the token to the backend and returns only the safe fields", async () => {
    cookieStore.get.mockReturnValue({ value: "tok-123" });
    fetchMock.mockResolvedValueOnce(answer({ ...ME, password_hash: "should-never-leak" }));

    const response = await GET();

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toEqual(ME);
    expect(body).not.toHaveProperty("password_hash");
    expect(response.headers.get("cache-control")).toBe("no-store");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/api/v1/auth/me");
    expect(init.headers.Authorization).toBe("Bearer tok-123");
  });

  it("removes the cookie when the backend no longer accepts the token", async () => {
    cookieStore.get.mockReturnValue({ value: "tok-123" });
    fetchMock.mockResolvedValueOnce(answer({ detail: "Not authenticated." }, 401));

    const response = await GET();

    expect(response.status).toBe(401);
    expect(cookieStore.set).toHaveBeenCalledWith(expect.objectContaining({ value: "", maxAge: 0 }));
  });

  it("keeps the cookie when the backend is merely down", async () => {
    cookieStore.get.mockReturnValue({ value: "tok-123" });
    fetchMock.mockRejectedValueOnce(new Error("connection refused"));

    const response = await GET();

    expect(response.status).toBe(502);
    expect(cookieStore.set).not.toHaveBeenCalled();
  });
});

describe("DELETE /api/session (log out)", () => {
  it("refuses a foreign site and keeps the cookie", async () => {
    const response = await DELETE(fakeRequest({ origin: "https://evil.example" }));

    expect(response.status).toBe(403);
    expect(cookieStore.set).not.toHaveBeenCalled();
  });

  it("clears the cookie for our own site", async () => {
    const response = await DELETE(fakeRequest());

    expect(response.status).toBe(200);
    expect(cookieStore.set).toHaveBeenCalledWith(
      expect.objectContaining({ name: "clinic_session", value: "", maxAge: 0, httpOnly: true }),
    );
  });
});