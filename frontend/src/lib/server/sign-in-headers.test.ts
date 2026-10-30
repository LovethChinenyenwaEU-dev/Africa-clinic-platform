import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { signInHeaders } from "./sign-in-headers";

function request(headers: Record<string, string>): Request {
  return { headers: new Headers(headers) } as unknown as Request;
}

describe("signInHeaders", () => {
  it("passes the browser's description and a real device id", () => {
    const id = "0b7c6f1e-2d3a-4c5b-8e9f-1a2b3c4d5e6f";

    expect(signInHeaders(request({ "user-agent": "Chrome/129", "x-device-id": id }))).toEqual({
      "User-Agent": "Chrome/129",
      "X-Device-Id": id,
    });
  });

  it("drops a device id that is not a UUID, and cuts a very long description", () => {
    const sent = signInHeaders(request({ "user-agent": "x".repeat(1000), "x-device-id": "abc" }));

    expect(sent["X-Device-Id"]).toBeUndefined();
    expect(sent["User-Agent"]).toHaveLength(300);
  });

  it("passes nothing when the browser sends nothing", () => {
    expect(signInHeaders(request({}))).toEqual({});
  });
});
