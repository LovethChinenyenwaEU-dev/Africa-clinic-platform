import { beforeEach, describe, expect, it, vi } from "vitest";

import { addBranch, newBranchSchema, publishWording, wordingProblem } from "./api";

const fetchMock = vi.fn();
const WORDING = {
  id: "11111111-1111-4111-8111-111111111111",
  purpose: "treatment",
  version: 2,
  body: "I agree to be treated.",
  created_at: "2026-11-02T09:00:00Z",
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
});

describe("branches", () => {
  it("needs a name; the city may be empty", () => {
    expect(newBranchSchema.safeParse({ name: "  ", city: "" }).success).toBe(false);
    expect(newBranchSchema.parse({ name: " Yaba ", city: "" })).toEqual({ name: "Yaba", city: "" });
  });

  it("adds a branch through the staff pass-through", async () => {
    fetchMock.mockResolvedValueOnce(
      answer({ id: WORDING.id, name: "Yaba", city: "Lagos" }, 201),
    );

    const branch = await addBranch({ name: "Yaba", city: "Lagos" });

    expect(branch.name).toBe("Yaba");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("/api/backend/tenancy/branches");
    expect(JSON.parse(init.body)).toEqual({ name: "Yaba", city: "Lagos" });
  });
});

describe("consent wording", () => {
  it("refuses empty, too long, or unchanged wording before asking the server", () => {
    expect(wordingProblem("  ", null)).toMatch(/Write the wording/);
    expect(wordingProblem("x".repeat(5001), null)).toMatch(/At most 5000/);
    expect(wordingProblem(" I agree to be treated. ", WORDING)).toMatch(/already in use/);
    expect(wordingProblem("I agree to be treated here.", WORDING)).toBeNull();
    expect(wordingProblem("First wording.", null)).toBeNull();
  });

  it("publishes trimmed wording for one purpose", async () => {
    fetchMock.mockResolvedValueOnce(answer({ ...WORDING, version: 3 }, 201));

    const published = await publishWording("treatment", "  New words.  ");

    expect(published.version).toBe(3);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("/api/backend/consent/texts");
    expect(JSON.parse(init.body)).toEqual({ purpose: "treatment", body: "New words." });
  });
});
