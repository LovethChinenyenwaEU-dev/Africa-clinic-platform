import { afterEach, describe, expect, it, vi } from "vitest";

import { isSameOrigin } from "./origin";

const CODESPACE = "https://effective-sniffle-abc-3000.app.github.dev";

function request(headers: Record<string, string>): Request {
  return { headers: new Headers(headers) } as unknown as Request;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("isSameOrigin", () => {
  it("accepts the site the server is really on", () => {
    expect(isSameOrigin(request({ origin: "http://localhost:3000", host: "localhost:3000" }))).toBe(
      true,
    );
  });

  it("refuses another site, and a request with no origin", () => {
    expect(isSameOrigin(request({ origin: "https://evil.example", host: "localhost:3000" }))).toBe(
      false,
    );
    expect(isSameOrigin(request({ host: "localhost:3000" }))).toBe(false);
  });

  it("refuses the Codespaces address until it is listed as trusted", () => {
    // The Codespaces proxy tells the app it is on localhost:3000.
    const fromCodespace = request({
      origin: CODESPACE,
      host: "localhost:3000",
      "x-forwarded-host": "localhost:3000",
    });

    expect(isSameOrigin(fromCodespace)).toBe(false);

    vi.stubEnv("TRUSTED_ORIGINS", `${CODESPACE}/`);
    expect(isSameOrigin(fromCodespace)).toBe(true);
  });

  it("trusts exact origins only: no look-alikes, no other ports, no other schemes", () => {
    vi.stubEnv("TRUSTED_ORIGINS", `${CODESPACE}, not a url ,`);

    for (const origin of [
      "https://effective-sniffle-abc-3000.app.github.dev.evil.example",
      "https://evil-3000.app.github.dev",
      "http://effective-sniffle-abc-3000.app.github.dev",
      "https://effective-sniffle-abc-3000.app.github.dev:8443",
    ]) {
      expect(isSameOrigin(request({ origin, host: "localhost:3000" }))).toBe(false);
    }
  });
});
