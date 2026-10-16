import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const { cookieStore } = vi.hoisted(() => ({
  cookieStore: { get: vi.fn(), set: vi.fn() },
}));
vi.mock("next/headers", () => ({ cookies: async () => cookieStore }));

import { MAX_BODY_BYTES, backendPath, forwardToBackend } from "./proxy";

const SITE = "http://localhost:3000";
const ID = "11111111-1111-4111-8111-111111111111";
const fetchMock = vi.fn();

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// A small stand-in for a browser request, so each test controls the headers.
function fakeRequest(
  options: { method?: string; url?: string; body?: string; origin?: string | null } = {},
): Request {
  const headers = new Headers({ host: "localhost:3000" });
  const origin = options.origin === undefined ? SITE : options.origin;
  if (origin) headers.set("origin", origin);
  return {
    method: options.method ?? "GET",
    url: options.url ?? `${SITE}/api/backend/encounters/${ID}`,
    headers,
    text: () => Promise.resolve(options.body ?? ""),
  } as unknown as Request;
}

function signedIn(token = "tok-123") {
  cookieStore.get.mockReturnValue({ value: token });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  process.env.API_INTERNAL_URL = "http://backend.test";
});

describe("backendPath", () => {
  it("joins plain segments", () => {
    expect(backendPath(["encounters", ID, "vitals"])).toBe(`/encounters/${ID}/vitals`);
  });

  it.each([
    [[]],
    [["auth", "login"]],
    [["encounters", ".."]],
    [["encounters", "."]],
    [["..", "admin"]],
    [["encounters", "a/b"]],
    [["encounters", "a%2Fb"]],
    [["encounters", ""]],
    [["encounters", "x y"]],
  ])("refuses unsafe paths: %j", (segments) => {
    expect(backendPath(segments)).toBeNull();
  });
});

describe("forwardToBackend", () => {
  it("forwards a read with the cookie's token and the query string", async () => {
    signedIn();
    fetchMock.mockResolvedValueOnce(answer([{ id: ID }]));

    const response = await forwardToBackend(
      fakeRequest({ url: `${SITE}/api/backend/encounters/${ID}/vitals?include_history=true` }),
      ["encounters", ID, "vitals"],
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([{ id: ID }]);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`http://backend.test/api/v1/encounters/${ID}/vitals?include_history=true`);
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer tok-123");
    expect(init.body).toBeUndefined();
  });

  it("forwards a write from our own site with its JSON body", async () => {
    signedIn();
    fetchMock.mockResolvedValueOnce(answer({ id: ID }, 201));

    const response = await forwardToBackend(
      fakeRequest({ method: "POST", body: '{"pulse_bpm":80}' }),
      ["encounters", ID, "vitals"],
    );

    expect(response.status).toBe(201);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"pulse_bpm":80}');
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("passes the Idempotency-Key on, and no other browser header", async () => {
    signedIn();
    fetchMock.mockResolvedValueOnce(answer({ id: ID }, 201));
    const request = fakeRequest({ method: "POST", body: "{}" });
    request.headers.set("idempotency-key", "11111111-aaaa-4bbb-8ccc-222222222222");
    request.headers.set("cookie", "clinic_session=secret");

    await forwardToBackend(request, ["encounters"]);

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Idempotency-Key"]).toBe("11111111-aaaa-4bbb-8ccc-222222222222");
    expect(Object.keys(init.headers).sort()).toEqual([
      "Authorization",
      "Content-Type",
      "Idempotency-Key",
    ]);
  });

  it("passes on a proper device ID, on reads and writes", async () => {
    signedIn();
    fetchMock.mockImplementation(async () => answer({ id: ID }));
    const device = "33333333-4444-4555-8666-777777777777";
    const read = fakeRequest();
    read.headers.set("x-device-id", device);

    await forwardToBackend(read, ["encounters", ID]);

    expect(fetchMock.mock.calls[0][1].headers["X-Device-Id"]).toBe(device);
  });

  it("drops a device ID that is not a proper UUID", async () => {
    signedIn();
    fetchMock.mockImplementation(async () => answer({ id: ID }));
    const read = fakeRequest();
    read.headers.set("x-device-id", "not-a-device; also-not-a-uuid");

    await forwardToBackend(read, ["encounters", ID]);

    expect(fetchMock.mock.calls[0][1].headers["X-Device-Id"]).toBeUndefined();
  });

  it("refuses writes that do not come from our own site", async () => {
    signedIn();

    const foreign = await forwardToBackend(
      fakeRequest({ method: "POST", origin: "https://evil.example" }),
      ["encounters"],
    );
    const missing = await forwardToBackend(fakeRequest({ method: "POST", origin: null }), [
      "encounters",
    ]);

    expect(foreign.status).toBe(403);
    expect(missing.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers 404 for unsafe paths without calling the backend", async () => {
    signedIn();

    const response = await forwardToBackend(fakeRequest(), ["auth", "me"]);

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers 401 when nobody is signed in", async () => {
    cookieStore.get.mockReturnValue(undefined);

    const response = await forwardToBackend(fakeRequest(), ["encounters", ID]);

    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses a body that is too large", async () => {
    signedIn();

    const response = await forwardToBackend(
      fakeRequest({ method: "POST", body: "x".repeat(MAX_BODY_BYTES + 1) }),
      ["encounters", ID, "notes"],
    );

    expect(response.status).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("clears the session when the backend no longer accepts the token", async () => {
    signedIn();
    fetchMock.mockResolvedValueOnce(answer({ detail: "Not authenticated." }, 401));

    const response = await forwardToBackend(fakeRequest(), ["encounters", ID]);

    expect(response.status).toBe(401);
    expect(cookieStore.set).toHaveBeenCalledWith(
      expect.objectContaining({ name: "clinic_session", value: "", maxAge: 0 }),
    );
  });

  it("passes the backend's own 4xx messages through", async () => {
    signedIn();
    fetchMock.mockResolvedValueOnce(
      answer({ detail: "Only the clinician who opened this encounter can do this." }, 403),
    );

    const response = await forwardToBackend(fakeRequest({ method: "POST" }), [
      "encounters",
      ID,
      "close",
    ]);

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({
      detail: "Only the clinician who opened this encounter can do this.",
    });
  });

  it("hides a backend crash behind a plain message", async () => {
    signedIn();
    fetchMock.mockResolvedValueOnce(answer({ detail: "Traceback: secret internals" }, 500));

    const response = await forwardToBackend(fakeRequest(), ["encounters", ID]);

    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("Traceback");
  });

  it("answers 502 when the backend cannot be reached", async () => {
    signedIn();
    fetchMock.mockRejectedValueOnce(new TypeError("fetch failed"));

    const response = await forwardToBackend(fakeRequest(), ["encounters", ID]);

    expect(response.status).toBe(502);
  });
});
