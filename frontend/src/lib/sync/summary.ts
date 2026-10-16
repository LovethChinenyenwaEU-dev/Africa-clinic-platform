import type { FlushResult } from "./outbox";
import type { OutboxItem } from "./store";

/*
 * What the screens say about the outbox. Kept apart from React so the wording and
 * the sign-out rule can be tested on their own.
 */

export type SyncView = {
  waiting: number; // this person's writes not yet sent
  failed: number; // this person's writes the server refused for good
  othersWaiting: number; // left on this device by someone whose session ended
  online: boolean;
  stopped: FlushResult["stopped"];
};

export type Tone = "ok" | "busy" | "warn" | "bad";

const entries = (count: number) => (count === 1 ? "1 entry" : `${count} entries`);

export function syncView(
  items: OutboxItem[],
  staffId: string,
  online: boolean,
  stopped: FlushResult["stopped"],
): SyncView {
  const mine = items.filter((item) => item.staffId === staffId);
  return {
    waiting: mine.filter((item) => item.status === "pending").length,
    failed: mine.filter((item) => item.status === "failed").length,
    othersWaiting: items.length - mine.length,
    online,
    stopped,
  };
}

/** The short line in the header. */
export function indicator(view: SyncView): { text: string; tone: Tone } {
  if (view.failed > 0) return { text: `${entries(view.failed)} not saved`, tone: "bad" };
  if (view.stopped === "signed_out" && view.waiting > 0) {
    return { text: `Sign in again to send ${entries(view.waiting)}`, tone: "bad" };
  }
  if (!view.online) {
    return {
      text: view.waiting > 0 ? `Offline · ${entries(view.waiting)} waiting` : "Offline",
      tone: "warn",
    };
  }
  if (view.waiting > 0) return { text: `${entries(view.waiting)} waiting to sync`, tone: "busy" };
  return { text: "All saved", tone: "ok" };
}

/**
 * Why this person may not sign out yet, or null. Signing out wipes patient data
 * from the device, so it waits until every write has reached the server, and
 * until any refused write has been looked at (Week 8 decision).
 */
export function signOutBlock(view: SyncView): string | null {
  if (view.waiting > 0) {
    return `${entries(view.waiting)} still waiting to sync. Stay connected until they are sent, then sign out.`;
  }
  if (view.failed > 0) {
    return `${entries(view.failed)} could not be saved. Open the sync list, read why, and dismiss them before signing out.`;
  }
  return null;
}
