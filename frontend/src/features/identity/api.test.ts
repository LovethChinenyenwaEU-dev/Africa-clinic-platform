import { beforeEach, describe, expect, it, vi } from "vitest";

import { LOGIN_MESSAGES, LoginError, login, logout } from "./api";

const fetchMock = vi.fn();
const FORM = { email: "nurse@example.com", password: "a-long-enough-password" };

function answerWith(status: number) {
  return new Response(JSON.stringify({}), { status });
}

async function failureOf(promise: Promise<unknown>) {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  return null;
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("login", () => {
  it("posts the form to our own session address", async () => {
    fetchMock.mockResolvedValueOnce(answerWith(200));

    await login(FORM);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/session");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(FORM);
  });

  it.each([
    [401, "wrong_login"],
    [422, "invalid_form"],
    [403, "refused"],
    [500, "unavailable"],
    [502, "unavailable"],
  ] as const)("turns a %s answer into the %s failure", async (status, kind) => {
    fetchMock.mockResolvedValueOnce(answerWith(status));

    const error = await failureOf(login(FORM));

    expect(error).toBeInstanceOf(LoginError);
    expect((error as LoginError).kind).toBe(kind);
  });

  it("treats a network failure as unavailable", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const error = await failureOf(login(FORM));

    expect((error as LoginError).kind).toBe("unavailable");
  });

  it("has a non-empty message for every kind of failure", () => {
    for (const message of Object.values(LOGIN_MESSAGES)) {
      expect(message.length).toBeGreaterThan(0);
    }
  });
});

describe("logout", () => {
  it("sends a DELETE to the session address", async () => {
    fetchMock.mockResolvedValueOnce(answerWith(200));

    await logout();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/session");
    expect(init.method).toBe("DELETE");
  });

  it("reports a failed sign-out", async () => {
    fetchMock.mockResolvedValueOnce(answerWith(502));

    await expect(logout()).rejects.toThrow("Could not sign out");
  });
});