import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  LOGIN_MESSAGES,
  LoginError,
  confirmAppSetup,
  groupSecret,
  login,
  logout,
  startAppSetup,
  verifyCode,
} from "./api";

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

  it("sends this device's id, so the sign-in shows in \"My devices\"", async () => {
    fetchMock.mockResolvedValueOnce(answerWith(200));

    await login(FORM);

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-Device-Id"]).toMatch(/^[0-9a-f-]{36}$/i);
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
describe("the authenticator step (admins and billing)", () => {
  function json(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status });
  }

  it("tells the form which step comes after the password", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ ok: true }))
      .mockResolvedValueOnce(json({ mfa: "verify" }))
      .mockResolvedValueOnce(json({ mfa: "setup" }));

    expect(await login(FORM)).toBe("done");
    expect(await login(FORM)).toBe("verify");
    expect(await login(FORM)).toBe("setup");
  });

  it("asks for the set-up key, then sends the first code and gets the backup codes", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ secret: "ABCDEFGHIJKL", otpauth_uri: "otpauth://x" }))
      .mockResolvedValueOnce(json({ ok: true, backup_codes: ["ABCD-EFGH", "JKLM-NPQR"] }));

    const setup = await startAppSetup();
    const codes = await confirmAppSetup("123456");

    expect(setup.secret).toBe("ABCDEFGHIJKL");
    expect(codes).toEqual(["ABCD-EFGH", "JKLM-NPQR"]);
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/session/mfa");
    expect(JSON.parse(init.body)).toEqual({ step: "confirm", code: "123456" });
  });

  it.each([
    [401, "wrong_code"],
    [429, "locked"],
    [409, "already_set_up"],
    [502, "unavailable"],
  ] as const)("turns a %s answer to a code into the %s failure", async (status, kind) => {
    fetchMock.mockResolvedValueOnce(json({}, status));

    const error = await failureOf(verifyCode("123456"));

    expect((error as LoginError).kind).toBe(kind);
  });

  it("says the step expired when the set-up key is refused", async () => {
    fetchMock.mockResolvedValueOnce(json({}, 401));

    const error = await failureOf(startAppSetup());

    expect((error as LoginError).kind).toBe("expired");
  });

  it("groups a long key in fours so it can be typed", () => {
    expect(groupSecret("ABCDEFGHIJKLMN")).toBe("ABCD EFGH IJKL MN");
  });
});
