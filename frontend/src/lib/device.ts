/*
 * This device's ID, so the audit diary can say which device a record was touched
 * from (FR-A2). It is a random UUID made once and kept on the device: not a
 * fingerprint, and it says nothing about the hardware or the person.
 *
 * It is deliberately kept at sign-out: it belongs to the device, not to whoever
 * used it. If storage is blocked, a fresh ID is used for this visit only.
 */

const KEY = "clinic.device-id";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

let fallback: string | null = null;

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // storage switched off or private browsing
  }
}

export function getDeviceId(): string {
  const store = storage();
  try {
    const saved = store?.getItem(KEY);
    if (saved && UUID.test(saved)) return saved;
    const made = crypto.randomUUID();
    store?.setItem(KEY, made);
    if (store) return made;
  } catch {
    // Could not read or write: fall through to the in-memory ID.
  }
  fallback ??= crypto.randomUUID();
  return fallback;
}
