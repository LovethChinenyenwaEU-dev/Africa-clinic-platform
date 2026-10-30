import "server-only";

/** Where the public landing page lives (landing/, its own app). LANDING_URL in .env. */
export function landingUrl(): string {
  return process.env.LANDING_URL || "http://localhost:3001";
}
