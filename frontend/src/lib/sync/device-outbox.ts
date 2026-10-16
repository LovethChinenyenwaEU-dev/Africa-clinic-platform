import { Outbox } from "./outbox";
import { indexedDbReadCache, memoryReadCache, type ReadCache } from "./read-cache";
import { indexedDbStore, memoryStore } from "./store";

/*
 * The one outbox and the one read cache for this browser tab. IndexedDB when the
 * browser has it; otherwise (very old browsers, server rendering) in memory, which
 * still works but cannot keep anything through a reload.
 */

// The query keys whose data a delivered write can change; they are re-read after a send.
export const SYNCED_QUERIES = [
  "vitals",
  "notes",
  "allergies",
  "problems",
  "encounter",
  "review-queue",
];

const hasIndexedDb = () => typeof indexedDB !== "undefined";

let shared: Outbox | null = null;
let reads: ReadCache | null = null;

export function deviceOutbox(): Outbox {
  shared ??= new Outbox(hasIndexedDb() ? indexedDbStore() : memoryStore());
  return shared;
}

export function deviceReadCache(): ReadCache {
  reads ??= hasIndexedDb() ? indexedDbReadCache() : memoryReadCache();
  return reads;
}
