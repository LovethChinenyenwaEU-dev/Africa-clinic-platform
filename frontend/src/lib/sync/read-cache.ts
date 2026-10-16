import { READS, done, finished, openDatabase } from "./database";

/*
 * Offline reads: a small copy of what this person last read, so the screens they
 * need during a visit still show without a network (Week 8 decision: minimal
 * patient data on the device).
 *
 * Kept: today's queue and visit list, branches, the clinician list, and the
 * encounters open on this device with their vitals, notes, prescriptions, allergies and problems,
 * plus the name and age of those encounters' patients. Never kept: patient search,
 * other patients' pages, consent, audit, history views.
 *
 * Wiped at sign-out, after 24 hours, and when someone else signs in on the device.
 */

export const KEEP_FOR_MS = 24 * 60 * 60 * 1000;

export type ReadEntry = {
  key: string; // the query key as JSON
  queryKey: unknown[];
  data: unknown;
  staffId: string;
  savedAt: number; // milliseconds, device clock
};

// Lists that are safe and useful to keep whole.
const ALWAYS = new Set(["queue", "day-list", "branches", "clinicians", "encounter"]);
// Encounter contents: kept, but not the "show earlier versions" view.
const CURRENT_ONLY = new Set(["vitals", "notes", "prescriptions", "follow-ups", "referrals"]);
// The patient's lists (allergies, problems) and details: only for an encounter kept here.
const BY_PATIENT = new Set(["allergies", "problems", "patient"]);

/** Whether a screen's read may be kept on the device. */
export function keepsOffline(queryKey: readonly unknown[], encounterPatients: Set<string>) {
  const [kind, id, history] = queryKey;
  if (typeof kind !== "string") return false;
  if (ALWAYS.has(kind)) return true;
  if (CURRENT_ONLY.has(kind)) return history !== true;
  if (BY_PATIENT.has(kind)) return typeof id === "string" && encounterPatients.has(id);
  return false;
}

/** Split saved reads into those still usable by this person, and those to delete. */
export function sortSaved(
  entries: ReadEntry[],
  staffId: string,
  now: number,
): { usable: ReadEntry[]; expired: string[] } {
  const usable: ReadEntry[] = [];
  const expired: string[] = [];
  for (const entry of entries) {
    const fresh = now - entry.savedAt < KEEP_FOR_MS && entry.savedAt <= now + 5 * 60 * 1000;
    if (fresh && entry.staffId === staffId) usable.push(entry);
    else expired.push(entry.key); // too old, from the future, or someone else's
  }
  return { usable, expired };
}

export interface ReadCache {
  put(entry: ReadEntry): Promise<void>;
  all(): Promise<ReadEntry[]>;
  remove(keys: string[]): Promise<void>;
  clear(): Promise<void>;
}

export function memoryReadCache(): ReadCache {
  const entries = new Map<string, ReadEntry>();
  return {
    async put(entry) {
      entries.set(entry.key, entry);
    },
    async all() {
      return [...entries.values()];
    },
    async remove(keys) {
      for (const key of keys) entries.delete(key);
    },
    async clear() {
      entries.clear();
    },
  };
}

export function indexedDbReadCache(): ReadCache {
  async function write(work: (store: IDBObjectStore) => void): Promise<void> {
    const transaction = (await openDatabase()).transaction(READS, "readwrite");
    work(transaction.objectStore(READS));
    await finished(transaction);
  }

  return {
    put: (entry) => write((store) => store.put(entry)),
    async all() {
      const transaction = (await openDatabase()).transaction(READS, "readonly");
      return (await done(transaction.objectStore(READS).getAll())) as ReadEntry[];
    },
    remove: (keys) => write((store) => keys.forEach((key) => store.delete(key))),
    clear: () => write((store) => store.clear()),
  };
}
