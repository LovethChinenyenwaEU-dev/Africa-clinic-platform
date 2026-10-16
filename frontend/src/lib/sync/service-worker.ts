/*
 * Starts the service worker (public/sw.js) that lets the app open offline, and
 * forgets the pages it kept when someone signs out.
 */

// Must match the page cache name in public/sw.js.
const PAGE_CACHE_PREFIX = "clinic-pages";

export function registerServiceWorker(): void {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  const mode = process.env.NODE_ENV === "production" ? "production" : "development";
  navigator.serviceWorker.register(`/sw.js?mode=${mode}`, { scope: "/" }).catch(() => {
    // Not allowed here (plain http on another host, private mode): the app still
    // works online, it just cannot open without a network.
  });
}

/** Delete the pages kept for offline opening: they show who was signed in. */
export async function forgetSavedPages(): Promise<void> {
  if (typeof caches === "undefined") return;
  const names = await caches.keys();
  await Promise.all(
    names.filter((name) => name.startsWith(PAGE_CACHE_PREFIX)).map((name) => caches.delete(name)),
  );
}
