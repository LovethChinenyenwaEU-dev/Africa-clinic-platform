import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { API_MESSAGES, ApiError, apiGet, apiPost } from "./index";

const fetchMock = vi.fn();
const thing = z.object({ id: z.string() });

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function failureOf(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) return error;
    throw error;
  }
  throw new Error("Expected the call to fail.");
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("apiGet and apiPost", () => {
  it("reads through our own pass-through and checks the answer", async () => {
    fetchMock.mockResolvedValueOnce(answer({ id: "a" }));

    expect(await apiGet("/encounters/a", thing)).toEqual({ id: "a" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/backend/encounters/a");
    expect(init.method).toBe("GET");
  });

  it("writes JSON", async () => {
    fetchMock.mockResolvedValueOnce(answer({ id: "b" }, 201));

    await apiPost("/encounters", { patient_id: "p" }, thing);

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ patient_id: "p" });
  });

  it("treats an answer of the wrong shape as unavailable, never as data", async () => {
    fetchMock.mockResolvedValueOnce(answer({ unexpected: true }));

    expect((await failureOf(apiGet("/x", thing))).kind).toBe("unavailable");
  });

  it.each([
    [401, "signed_out"],
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
    [413, "invalid"],
    [422, "invalid"],
    [502, "unavailable"],
  ])("turns status %i into %s", async (status, kind) => {
    fetchMock.mockResolvedValueOnce(answer({}, status));

    expect((await failureOf(apiGet("/x", thing))).kind).toBe(kind);
  });

  it("shows the backend's own message for a refusal or a conflict", async () => {
    fetchMock.mockResolvedValueOnce(
      answer({ detail: "Only the clinician who opened this encounter can do this." }, 403),
    );

    const error = await failureOf(apiPost("/encounters/a/close", {}, thing));

    expect(error.message).toBe("Only the clinician who opened this encounter can do this.");
  });

  it("does not show FastAPI's technical form errors or a 404's wording", async () => {
    fetchMock.mockResolvedValueOnce(answer({ detail: [{ loc: ["body"], msg: "x" }] }, 422));
    fetchMock.mockResolvedValueOnce(answer({ detail: "Patient not found." }, 404));

    expect((await failureOf(apiGet("/x", thing))).message).toBe(API_MESSAGES.invalid);
    expect((await failureOf(apiGet("/x", thing))).message).toBe(API_MESSAGES.not_found);
  });

  it("reports a network failure as unavailable", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    expect((await failureOf(apiGet("/x", thing))).kind).toBe("unavailable");
  });
});

describe("ApiError.detail", () => {
  it("carries the backend's structured detail for screens that understand it", async () => {
    const warning = { message: "This patient may already be registered.", matches: [] };
    fetchMock.mockResolvedValueOnce(answer({ detail: warning }, 409));

    const error = await failureOf(apiPost("/patients", {}, thing));

    expect(error.kind).toBe("conflict");
    expect(error.detail).toEqual(warning);
    expect(error.message).toBe(API_MESSAGES.conflict); // an object is never shown raw
  });
});

describe("errorMessage", () => {
  it("shows our own message, and a plain one for anything else", async () => {
    const { errorMessage } = await import("./index");
    expect(errorMessage(new ApiError("forbidden", "Only the author can amend."))).toBe(
      "Only the author can amend.",
    );
    expect(errorMessage(new TypeError("internal details"))).toBe(API_MESSAGES.unavailable);
  });
});

describe("device ID", () => {
  it("is sent on every request, reads and writes alike", async () => {
    fetchMock.mockImplementation(async () => answer({ id: "a" }));

    await apiGet("/x", thing);
    await apiPost("/x", {}, thing);

    for (const [, init] of fetchMock.mock.calls) {
      expect(init.headers["X-Device-Id"]).toMatch(/^[0-9a-f-]{36}$/);
    }
    expect(fetchMock.mock.calls[1][1].headers["Content-Type"]).toBe("application/json");
  });
});

describe("idempotency key", () => {
  it("is sent only when given, beside the device ID", async () => {
    fetchMock.mockImplementation(async () => answer({ id: "a" }, 201));
    const key = "66666666-7777-4888-8999-aaaaaaaaaaaa";

    await apiPost("/x", {}, thing, { idempotencyKey: key });
    await apiPost("/x", {}, thing);

    expect(fetchMock.mock.calls[0][1].headers["Idempotency-Key"]).toBe(key);
    expect(fetchMock.mock.calls[0][1].headers["X-Device-Id"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(fetchMock.mock.calls[1][1].headers["Idempotency-Key"]).toBeUndefined();
  });
});
