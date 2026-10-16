import { describe, expect, it } from "vitest";

import {
  KEEP_FOR_MS,
  keepsOffline,
  memoryReadCache,
  sortSaved,
  type ReadEntry,
} from "./read-cache";

const ME = "77777777-7777-4777-8777-777777777777";
const SOMEONE_ELSE = "88888888-8888-4888-8888-888888888888";
const IN_VISIT = "11111111-1111-4111-8111-111111111111";
const OTHER_PATIENT = "22222222-2222-4222-8222-222222222222";
const ENCOUNTER = "33333333-3333-4333-8333-333333333333";
const NOW = Date.parse("2026-10-16T12:00:00Z");

function entry(changes: Partial<ReadEntry> = {}): ReadEntry {
  return {
    key: JSON.stringify(["queue", "b1"]),
    queryKey: ["queue", "b1"],
    data: [],
    staffId: ME,
    savedAt: NOW - 60_000,
    ...changes,
  };
}

describe("keepsOffline", () => {
  const visiting = new Set([IN_VISIT]);

  it.each([
    [["queue", "b1"]],
    [["day-list", "b1", "2026-10-16"]],
    [["branches"]],
    [["clinicians"]],
    [["encounter", ENCOUNTER]],
    [["vitals", ENCOUNTER, false]],
    [["notes", ENCOUNTER, false]],
    [["allergies", IN_VISIT]],
    [["problems", IN_VISIT]],
    [["patient", IN_VISIT]],
  ])("keeps %j", (key) => {
    expect(keepsOffline(key, visiting)).toBe(true);
  });

  it.each([
    [["vitals", ENCOUNTER, true]], // earlier versions: not needed during a visit
    [["notes", ENCOUNTER, true]],
    [["patient", OTHER_PATIENT]], // a patient with no encounter on this device
    [["allergies", OTHER_PATIENT]],
    [["patients", "search", "Ada"]],
    [["consent-history", IN_VISIT]],
    [["audit", "x"]],
    [["staff"]],
  ])("never keeps %j", (key) => {
    expect(keepsOffline(key, visiting)).toBe(false);
  });
});

describe("sortSaved", () => {
  it("keeps this person's copies younger than 24 hours", () => {
    const fresh = entry();

    expect(sortSaved([fresh], ME, NOW)).toEqual({ usable: [fresh], expired: [] });
  });

  it("drops copies older than 24 hours, someone else's, and ones dated in the future", () => {
    const old = entry({ key: "old", savedAt: NOW - KEEP_FOR_MS });
    const theirs = entry({ key: "theirs", staffId: SOMEONE_ELSE });
    const future = entry({ key: "future", savedAt: NOW + 60 * 60 * 1000 });

    expect(sortSaved([old, theirs, future], ME, NOW)).toEqual({
      usable: [],
      expired: ["old", "theirs", "future"],
    });
  });
});

describe("memoryReadCache", () => {
  it("saves, replaces, removes and clears", async () => {
    const cache = memoryReadCache();
    await cache.put(entry({ key: "a", data: 1 }));
    await cache.put(entry({ key: "a", data: 2 }));
    await cache.put(entry({ key: "b" }));

    expect((await cache.all()).map((saved) => saved.data)).toEqual([2, []]);
    await cache.remove(["a"]);
    expect((await cache.all()).map((saved) => saved.key)).toEqual(["b"]);
    await cache.clear();
    expect(await cache.all()).toEqual([]);
  });
});
