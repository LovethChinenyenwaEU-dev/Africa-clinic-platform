import "server-only";

import { z } from "zod";

export const REQUEST_TIMEOUT_MS = 10_000;

/** The backend could not be reached, or sent something we did not expect. */
export class BackendUnavailableError extends Error {}

/** The backend answered, but said no (for example 401 for a wrong password). */
export class BackendRejectedError extends Error {
  constructor(readonly status: number) {
    super(`The backend answered ${status}.`);
  }
}

export function apiBase(): string {
  const url = process.env.API_INTERNAL_URL;
  if (!url) {
    throw new BackendUnavailableError("API_INTERNAL_URL is not set.");
  }
  return `${url.replace(/\/$/, "")}/api/v1`;
}

/** Call the backend and check the answer's shape with Zod before anyone uses it. */
export async function callBackend<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    throw new BackendUnavailableError("The backend could not be reached.");
  }

  if (!response.ok) {
    throw new BackendRejectedError(response.status);
  }

  const parsed = schema.safeParse(await response.json().catch(() => null));
  if (!parsed.success) {
    throw new BackendUnavailableError("The backend sent an unexpected answer.");
  }
  return parsed.data;
}