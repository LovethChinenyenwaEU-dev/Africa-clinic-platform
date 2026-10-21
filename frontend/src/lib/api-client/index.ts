import { z } from "zod";

import { getDeviceId } from "@/lib/device";

/*
 * How screens talk to the API: always through our own /api/backend pass-through,
 * which adds the login token on the server. Every answer is checked with Zod
 * before a screen uses it.
 */

const BASE = "/api/backend";

export type ApiFailure =
  | "signed_out"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "invalid"
  | "unavailable";

// What a person sees when the server gave no message we can show.
export const API_MESSAGES: Record<ApiFailure, string> = {
  signed_out: "Your session has ended. Please sign in again.",
  forbidden: "You do not have permission to do this.",
  not_found: "Not found.",
  conflict: "This changed in the meantime. Reload and try again.",
  invalid: "Check the form and try again.",
  unavailable: "The service is unavailable. Please try again.",
};

export class ApiError extends Error {
  constructor(
    readonly kind: ApiFailure,
    message: string = API_MESSAGES[kind],
    // The backend's raw `detail`, for screens that understand a structured answer
    // (for example the possible-duplicate warning). Check it with Zod before use.
    readonly detail: unknown = undefined,
  ) {
    super(message);
  }
}

function kindFor(status: number): ApiFailure {
  if (status === 401) return "signed_out";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 413 || status === 422) return "invalid";
  return "unavailable";
}

// Our backend writes its 403/409/422 messages for staff, with no clinical text,
// so they are worth showing. FastAPI's own form errors are a list: too technical.
const SHOWN_KINDS: ReadonlySet<ApiFailure> = new Set(["forbidden", "conflict", "invalid"]);

function messageFrom(body: unknown, kind: ApiFailure): string {
  if (SHOWN_KINDS.has(kind) && body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.length > 0 && detail.length <= 300) {
      return detail;
    }
  }
  return API_MESSAGES[kind];
}

async function send<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit,
  base: string = BASE,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      // Every request says which device it came from, for the audit diary (FR-A2).
      headers: { ...(init.headers as Record<string, string>), "X-Device-Id": getDeviceId() },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("unavailable");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const kind = kindFor(response.status);
    const detail =
      body && typeof body === "object" ? (body as { detail?: unknown }).detail : undefined;
    throw new ApiError(kind, messageFrom(body, kind), detail);
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError("unavailable");
  }
  return parsed.data;
}

/** Read from the API, for example apiGet("/patients/123", patientSchema). */
export function apiGet<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  return send(path, schema, { method: "GET" });
}

export type PostOptions = {
  // The same key on a re-send makes the server answer as it did the first time,
  // without doing the work twice (Week 8). The outbox sends one per queued write.
  idempotencyKey?: string;
};

/** Write to the API. The body is sent as JSON. */
export function apiPost<T>(
  path: string,
  body: unknown,
  schema: z.ZodType<T>,
  options: PostOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
  return send(path, schema, {
    method: "POST",
    headers,
    body: JSON.stringify(body ?? {}),
  });
}

/** The words to show a person for any failure, never anything raw. */
export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : API_MESSAGES.unavailable;
}

// The patient's own pages (Week 9) go through their own pass-through, with the
// patient's cookie. Same checks on every answer as the staff screens.
const PATIENT_BASE = "/api/patient";

export function patientGet<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  return send(path, schema, { method: "GET" }, PATIENT_BASE);
}

export function patientPost<T>(path: string, body: unknown, schema: z.ZodType<T>): Promise<T> {
  return send(
    path,
    schema,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    },
    PATIENT_BASE,
  );
}
