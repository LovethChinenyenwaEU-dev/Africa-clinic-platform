/** True only when the request clearly came from our own website. */
export function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  const forwarded = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = forwarded || request.headers.get("host");
  if (!origin || !host) {
    return false;
  }
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}