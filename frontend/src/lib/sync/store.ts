/*
 * Where queued writes wait on the device until they reach the server.
 *
 * In the browser this is IndexedDB, which survives a reload, a closed tab and a
 * flat battery. Tests use the in-memory store: same behaviour, no browser needed.
 *
 * What is stored is only what the write itself needs (the address and the form),
 * nothing read from the server. The outbox is emptied as writes are delivered, and
 * sign-out is blocked while anything is still waiting (Week 8 decision).
 */

import { OUTBOX, done, finished, openDatabase } from "./database";

export type OutboxStatus = "pending" | "failed";

export type OutboxItem = {
  seq: number; // order of arrival on this device; writes are sent in this order
  id: string; // sent as the Idempotency-Key, so a re-send is never done twice
  path: string; // for example /encounters/{id}/vitals
  body: unknown;
  label: string; // plain words for the screen, never clinical text: "Vitals"
  staffId: string; // who made it: only their own session ever sends it
  encounterId: string | null; // so a screen can show what is still waiting for it
  createdAt: string; // ISO time, on the device clock
  attempts: number;
  status: OutboxStatus;
  error: string | null; // the server's reason, when it refused for good
};

export type NewOutboxItem = Omit<OutboxItem, "seq">;

export interface OutboxStore {
  add(item: NewOutboxItem): Promise<OutboxItem>;
  /** Everything waiting, oldest first. */
  list(): Promise<OutboxItem[]>;
  put(item: OutboxItem): Promise<void>;
  remove(seq: number): Promise<void>;
}

export function memoryStore(): OutboxStore {
  const items = new Map<number, OutboxItem>();
  let last = 0;
  return {
    async add(item) {
      last += 1;
      const saved = { ...item, seq: last };
      items.set(last, saved);
      return { ...saved };
    },
    async list() {
      return [...items.values()].sort((a, b) => a.seq - b.seq).map((item) => ({ ...item }));
    },
    async put(item) {
      if (items.has(item.seq)) items.set(item.seq, { ...item });
    },
    async remove(seq) {
      items.delete(seq);
    },
  };
}

export function indexedDbStore(): OutboxStore {
  async function write(work: (store: IDBObjectStore) => void): Promise<void> {
    const transaction = (await openDatabase()).transaction(OUTBOX, "readwrite");
    work(transaction.objectStore(OUTBOX));
    await finished(transaction);
  }

  return {
    async add(item) {
      const transaction = (await openDatabase()).transaction(OUTBOX, "readwrite");
      const seq = await done(transaction.objectStore(OUTBOX).add(item));
      await finished(transaction);
      return { ...item, seq: Number(seq) };
    },
    async list() {
      const transaction = (await openDatabase()).transaction(OUTBOX, "readonly");
      return (await done(transaction.objectStore(OUTBOX).getAll())) as OutboxItem[];
    },
    async put(item) {
      await write((store) => store.put(item));
    },
    async remove(seq) {
      await write((store) => store.delete(seq));
    },
  };
}
