/**
 * Extra exact origins we trust, from TRUSTED_ORIGINS (comma separated), for when a
 * proxy hides our real address. GitHub Codespaces, for example, tells the app it is
 * on localhost:3000 while the browser is on https://<name>-3000.app.github.dev.
 * Exact matches only, never wildcards, so a look-alike site can never get in.
 */
function trustedOrigins(): Set<string> {
  const listed = (process.env.TRUSTED_ORIGINS ?? "").split(",");
  const origins = new Set<string>();
  for (const entry of listed) {
    try {
      if (entry.trim()) origins.add(new URL(entry.trim()).origin);
    } catch {
      // A malformed entry is ignored, never treated as "trust everything".
    }
  }
  return origins;
}

function check(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) {
    return false;
  }
  let originUrl: URL;
  try {
    originUrl = new URL(origin);
  } catch {
    return false;
  }
  if (trustedOrigins().has(originUrl.origin)) {
    return true;
  }
  // A proxy may leave either header holding our address: Codespaces, for one, rewrites
  // Origin to localhost and keeps the real address in x-forwarded-host. Matching either
  // stays safe, because a cross-site page cannot fake Origin: it is always the
  // attacker's own site, which never equals our host.
  const forwarded = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const ours = [forwarded, request.headers.get("host")].filter(Boolean);
  return ours.includes(originUrl.host);
}

/** True only when the request clearly came from our own website. */
export function isSameOrigin(request: Request): boolean {
  const allowed = check(request);
  if (!allowed && process.env.NODE_ENV === "development") {
    // Development only: say why, so a proxy that hides our address is easy to spot.
    // Addresses only, never bodies, cookies or anything about a person.
    console.warn("[origin-check] refused", {
      origin: request.headers.get("origin"),
      host: request.headers.get("host"),
      forwardedHost: request.headers.get("x-forwarded-host"),
      trusted: [...trustedOrigins()],
    });
  }
  return allowed;
}
