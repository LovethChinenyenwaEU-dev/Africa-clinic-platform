import "server-only";

import { cookies } from "next/headers";

export const SESSION_COOKIE = "clinic_session";
// Patients have their own cookie (Week 9), so a patient and a staff member signed in
// on the same browser never share a session, and neither token can reach the other's pages.
export const PATIENT_SESSION_COOKIE = "clinic_patient_session";

// Matches the backend tokens' life (30 minutes).
export const SESSION_MAX_AGE_SECONDS = 30 * 60;

export type CookieSession = {
  read: () => Promise<string | null>;
  write: (token: string) => Promise<void>;
  clear: () => Promise<void>;
};

function cookieSession(name: string, maxAge: number = SESSION_MAX_AGE_SECONDS): CookieSession {
  // Worked out each time a cookie is written, not once when this file loads,
  // so "Secure" always follows the environment the server is running in.
  const options = () => ({
    name,
    httpOnly: true, // JavaScript cannot read it
    secure: process.env.NODE_ENV === "production", // HTTPS only when deployed
    sameSite: "lax" as const, // not sent when another website tricks the browser
    path: "/",
  });
  return {
    async read() {
      const store = await cookies();
      return store.get(name)?.value ?? null;
    },
    async write(token) {
      const store = await cookies();
      store.set({ ...options(), value: token, maxAge });
    },
    async clear() {
      const store = await cookies();
      store.set({ ...options(), value: "", maxAge: 0 });
    },
  };
}

export const staffSession = cookieSession(SESSION_COOKIE);
export const patientSession = cookieSession(PATIENT_SESSION_COOKIE);

// Between the password and the authenticator code (Week 11): the 5-minute challenge the
// backend gives admins and billing. Kept in its own httpOnly cookie, so the page's
// JavaScript never holds it, and it opens nothing but the code step.
export const MFA_CHALLENGE_COOKIE = "clinic_mfa_challenge";
export const MFA_CHALLENGE_SECONDS = 5 * 60;
export const challengeSession = cookieSession(MFA_CHALLENGE_COOKIE, MFA_CHALLENGE_SECONDS);

// The staff names used across the app since Week 7.
export const readSessionToken = staffSession.read;
export const writeSessionToken = staffSession.write;
export const clearSession = staffSession.clear;
