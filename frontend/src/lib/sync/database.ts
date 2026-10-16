/*
 * The device database (IndexedDB) that keeps offline work.
 *
 * - outbox: writes waiting to reach the server (Step 5).
 * - reads: a small copy of what this person last read, so today's queue and the
 *   encounters open on this device can be shown without a network (Step 7). Wiped
 *   at sign-out and after 24 hours.
 *
 * Raise DB_VERSION when adding a store; the upgrade below only adds what is missing.
 */

const DB_NAME = "clinic-offline";
const DB_VERSION = 2;
export const OUTBOX = "outbox";
export const READS = "reads";

export function done<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export function finished(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
}

let opening: Promise<IDBDatabase> | null = null;

export function openDatabase(): Promise<IDBDatabase> {
  opening ??= new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(OUTBOX)) {
        // The key grows with every write, so reading in key order is arrival order,
        // whatever the device clock says.
        const store = db.createObjectStore(OUTBOX, { keyPath: "seq", autoIncrement: true });
        store.createIndex("id", "id", { unique: true });
      }
      if (!db.objectStoreNames.contains(READS)) {
        db.createObjectStore(READS, { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  }).catch((error) => {
    opening = null; // let a later call try again
    throw error;
  });
  return opening;
}
