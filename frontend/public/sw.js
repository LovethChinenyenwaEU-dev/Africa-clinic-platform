/*
 * Service worker: lets the app open with no network (Week 8, Step 7b).
 *
 * What it keeps, in the browser's Cache Storage:
 * - The app's own files (/_next/static): scripts and styles.
 * - Pages already opened on this device. Our pages carry no patient data in their
 *   HTML (screens load it in the browser), only the signed-in staff member's name.
 *   They are deleted at sign-out.
 *
 * What it never touches: the API (/api/...), which goes to the network as usual;
 * patient data kept for offline use is handled by the app itself, with its own
 * rules (read-cache.ts). Also never: anything that is not a GET, or another site.
 *
 * Pages: network first. If the network fails, or is too slow to answer within a few
 * seconds, the copy kept here is shown; with no copy, a plain offline page.
 */

const VERSION = "v1";
const STATIC_CACHE = `clinic-static-${VERSION}`;
const PAGE_CACHE = `clinic-pages-${VERSION}`; // the app deletes "clinic-pages*" at sign-out
const OFFLINE_PAGE = "/offline.html";
const SLOW_NETWORK_MS = 6000;

// In development the app's files change without changing their names, so they are
// always fetched first; in production their names change with their content.
const DEVELOPMENT = new URL(self.location.href).searchParams.get("mode") !== "production";

/** What kind of request this is, and so how it is handled. */
function requestKind({ url, method, mode, headers, origin }) {
  const address = new URL(url);
  if (method !== "GET" || address.origin !== origin) return "ignore";
  if (address.pathname.startsWith("/api/")) return "ignore";
  // Next.js page data for in-app navigation: if it fails, the app falls back to a
  // full page load, which is handled below.
  if (headers.get("RSC") || headers.get("Next-Router-Prefetch") || address.searchParams.has("_rsc")) {
    return "ignore";
  }
  if (address.pathname.startsWith("/_next/static/") || address.pathname === OFFLINE_PAGE) {
    return "static";
  }
  if (mode === "navigate") return "page";
  return "ignore";
}

/** Only a real page from our own site is kept: never an error or a redirect (e.g. to sign in). */
function canKeepPage(response) {
  return (
    response.ok &&
    !response.redirected &&
    response.type === "basic" &&
    (response.headers.get("Content-Type") || "").includes("text/html")
  );
}

// Exposed so the rules can be tested; harmless in the browser.
self.clinicSw = { requestKind, canKeepPage };

async function staticFile(request) {
  const cache = await caches.open(STATIC_CACHE);
  if (!DEVELOPMENT) {
    const kept = await cache.match(request);
    if (kept) return kept;
  }
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch (error) {
    const kept = await cache.match(request);
    if (kept) return kept;
    throw error;
  }
}

function slow(ms) {
  return new Promise((resolve) => setTimeout(() => resolve(null), ms));
}

async function page(request) {
  const cache = await caches.open(PAGE_CACHE);
  const fromNetwork = fetch(request).then(async (response) => {
    if (canKeepPage(response)) await cache.put(request.url, response.clone());
    return response;
  });

  // A slow network: show the kept copy rather than a blank screen, if there is one.
  const first = await Promise.race([fromNetwork.catch(() => null), slow(SLOW_NETWORK_MS)]);
  if (first) return first;
  const kept = await cache.match(request.url);
  if (kept) return kept;
  try {
    return await fromNetwork;
  } catch {
    return (await caches.match(OFFLINE_PAGE)) || Response.error();
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.add(OFFLINE_PAGE))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  const current = new Set([STATIC_CACHE, PAGE_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith("clinic-") && !current.has(name))
            .map((name) => caches.delete(name)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const kind = requestKind({
    url: request.url,
    method: request.method,
    mode: request.mode,
    headers: request.headers,
    origin: self.location.origin,
  });
  if (kind === "static") event.respondWith(staticFile(request));
  else if (kind === "page") event.respondWith(page(request));
  // Everything else goes to the network untouched.
});
