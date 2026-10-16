import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

import { describe, expect, it } from "vitest";

/*
 * Loads the real public/sw.js in a bare sandbox and checks its rules: what it
 * handles, and what it must never keep (the API, other sites, errors, redirects).
 */

type Kind = "ignore" | "static" | "page";
type Rules = {
  requestKind: (request: {
    url: string;
    method: string;
    mode: string;
    headers: Headers;
    origin: string;
  }) => Kind;
  canKeepPage: (response: Response) => boolean;
};

const SITE = "https://clinic.example";

function loadRules(): Rules {
  const code = readFileSync(new URL("../../../public/sw.js", import.meta.url), "utf8");
  const self: Record<string, unknown> = {
    location: { href: `${SITE}/sw.js?mode=development`, origin: SITE },
    addEventListener: () => {},
  };
  runInNewContext(code, { self, URL, Headers, Response, Promise, setTimeout });
  return self.clinicSw as Rules;
}

const rules = loadRules();

function kind(path: string, changes: { method?: string; mode?: string; headers?: object } = {}) {
  return rules.requestKind({
    url: path.startsWith("http") ? path : `${SITE}${path}`,
    method: changes.method ?? "GET",
    mode: changes.mode ?? "cors",
    headers: new Headers((changes.headers ?? {}) as Record<string, string>),
    origin: SITE,
  });
}

describe("which requests the service worker handles", () => {
  it("keeps pages opened by the browser", () => {
    expect(kind("/encounters/123", { mode: "navigate" })).toBe("page");
    expect(kind("/queue", { mode: "navigate" })).toBe("page");
  });

  it("keeps the app's own files and the offline page", () => {
    expect(kind("/_next/static/chunks/app.js")).toBe("static");
    expect(kind("/offline.html")).toBe("static");
  });

  it("never touches the API, even when the browser opens it as a page", () => {
    expect(kind("/api/backend/encounters/123")).toBe("ignore");
    expect(kind("/api/session", { mode: "navigate" })).toBe("ignore");
  });

  it("leaves writes, other sites and in-app page data to the network", () => {
    expect(kind("/queue", { method: "POST", mode: "navigate" })).toBe("ignore");
    expect(kind("https://elsewhere.example/x.js")).toBe("ignore");
    expect(kind("/queue", { headers: { RSC: "1" } })).toBe("ignore");
    expect(kind("/queue?_rsc=abc")).toBe("ignore");
    expect(kind("/queue", { headers: { "Next-Router-Prefetch": "1" } })).toBe("ignore");
  });
});

describe("which pages are kept", () => {
  const html = { "Content-Type": "text/html; charset=utf-8" };

  function response(body: string, init: ResponseInit, redirected = false): Response {
    const real = new Response(body, init);
    // The sandbox needs only these four fields; a Response made here is not "basic".
    return {
      ok: real.ok,
      redirected,
      type: "basic",
      headers: real.headers,
    } as unknown as Response;
  }

  it("keeps a page that loaded", () => {
    expect(rules.canKeepPage(response("<html>", { status: 200, headers: html }))).toBe(true);
  });

  it("never keeps an error, a redirect (for example to sign in), or something not a page", () => {
    expect(rules.canKeepPage(response("", { status: 500, headers: html }))).toBe(false);
    expect(rules.canKeepPage(response("<html>", { status: 200, headers: html }, true))).toBe(
      false,
    );
    expect(
      rules.canKeepPage(
        response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
      ),
    ).toBe(false);
  });
});
