import { describe, expect, it } from "vitest";

import type { OutboxItem } from "./store";
import { indicator, signOutBlock, syncView, type SyncView } from "./summary";

const ME = "77777777-7777-4777-8777-777777777777";
const SOMEONE_ELSE = "88888888-8888-4888-8888-888888888888";

let seq = 0;
function item(changes: Partial<OutboxItem> = {}): OutboxItem {
  seq += 1;
  return {
    seq,
    id: crypto.randomUUID(),
    path: "/x",
    body: {},
    label: "Vitals",
    staffId: ME,
    encounterId: null,
    createdAt: "2026-10-16T09:00:00Z",
    attempts: 0,
    status: "pending",
    error: null,
    ...changes,
  };
}

const CALM: SyncView = { waiting: 0, failed: 0, othersWaiting: 0, online: true, stopped: null };

describe("syncView", () => {
  it("counts this person's waiting and refused writes, and others' apart", () => {
    const items = [
      item(),
      item(),
      item({ status: "failed", error: "No." }),
      item({ staffId: SOMEONE_ELSE }),
    ];

    expect(syncView(items, ME, false, "offline")).toEqual({
      waiting: 2,
      failed: 1,
      othersWaiting: 1,
      online: false,
      stopped: "offline",
    });
  });
});

describe("indicator", () => {
  it.each<[Partial<SyncView>, string, string]>([
    [{}, "All saved", "ok"],
    [{ waiting: 1 }, "1 entry waiting to sync", "busy"],
    [{ online: false }, "Offline", "warn"],
    [{ online: false, waiting: 3 }, "Offline · 3 entries waiting", "warn"],
    [{ waiting: 2, stopped: "signed_out" }, "Sign in again to send 2 entries", "bad"],
    [{ failed: 1, waiting: 4, online: false }, "1 entry not saved", "bad"],
  ])("%j reads %s", (changes, text, tone) => {
    expect(indicator({ ...CALM, ...changes })).toEqual({ text, tone });
  });
});

describe("signOutBlock", () => {
  it("allows sign-out only when nothing of this person's is left on the device", () => {
    expect(signOutBlock(CALM)).toBeNull();
    expect(signOutBlock({ ...CALM, othersWaiting: 2 })).toBeNull(); // not theirs to wait for
  });

  it("waits for writes still to be sent", () => {
    expect(signOutBlock({ ...CALM, waiting: 2 })).toContain("2 entries still waiting to sync");
  });

  it("asks for refused writes to be read and dismissed first", () => {
    expect(signOutBlock({ ...CALM, failed: 1 })).toContain("1 entry could not be saved");
  });
});
