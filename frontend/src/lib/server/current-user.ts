import "server-only";

import { meSchema, type Me } from "@/features/identity/schemas";

import { BackendRejectedError, callBackend } from "./backend";
import { readSessionToken } from "./session";

/**
 * The signed-in person, or null if nobody is signed in or the backend no longer
 * accepts the session. If the backend is unreachable this throws, so an outage
 * is not mistaken for "signed out".
 */
export async function getCurrentUser(): Promise<Me | null> {
  const token = await readSessionToken();
  if (!token) {
    return null;
  }

  try {
    return await callBackend("/auth/me", meSchema, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (error) {
    if (error instanceof BackendRejectedError && error.status === 401) {
      return null;
    }
    throw error;
  }
}