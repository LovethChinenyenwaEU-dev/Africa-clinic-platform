import "server-only";

import { cookies } from "next/headers";

export const SESSION_COOKIE = "clinic_session";

// Matches the backend token's life (30 minutes).
export const SESSION_MAX_AGE_SECONDS = 30 * 60;

function baseOptions() {
  return {
    name: SESSION_COOKIE,
    httpOnly: true, // JavaScript cannot read it
    secure: process.env.NODE_ENV === "production", // HTTPS only when deployed
    sameSite: "lax" as const, // not sent when another website tricks the browser
    path: "/",
  };
}

export async function readSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export async function writeSessionToken(token: string): Promise<void> {
  const store = await cookies();
  store.set({ ...baseOptions(), value: token, maxAge: SESSION_MAX_AGE_SECONDS });
}

export async function clearSession(): Promise<void> {
  const store = await cookies();
  store.set({ ...baseOptions(), value: "", maxAge: 0 });
}