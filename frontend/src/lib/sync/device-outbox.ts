import { Outbox } from "./outbox";
import { indexedDbStore, memoryStore } from "./store";

/*
 * The one outbox for this browser tab. IndexedDB when the browser has it; otherwise
 * (very old browsers, server rendering) an in-memory one, which still sends writes
 * but cannot keep them through a reload.
 */

// The query keys whose data a delivered write can change; they are re-read after a send.
export const SYNCED_QUERIES = ["vitals", "notes", "allergies", "problems", "encounter"];

let shared: Outbox | null = null;

export function deviceOutbox(): Outbox {
  shared ??= new Outbox(typeof indexedDB === "undefined" ? memoryStore() : indexedDbStore());
  return shared;
}
