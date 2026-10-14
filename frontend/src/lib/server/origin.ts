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

/** True only when the request clearly came from our own website. */
export function isSameOrigin(request: Request): boolean {
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
  const forwarded = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = forwarded || request.headers.get("host");
  return Boolean(host) && originUrl.host === host;
}
