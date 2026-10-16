import "server-only";

import { NextResponse } from "next/server";

import { REQUEST_TIMEOUT_MS, apiBase } from "./backend";
import { isSameOrigin } from "./origin";
import { clearSession, readSessionToken } from "./session";

/*
 * The pass-through between our screens and the API.
 *
 * The browser never holds the login token: it sits in an httpOnly cookie, and
 * this code adds it on the way to the backend. Everything that keeps that safe
 * is in this one file.
 */

// Only plain names like "encounters" or a UUID. Never "..", slashes or odd characters.
const SAFE_SEGMENT = /^[A-Za-z0-9_-][A-Za-z0-9_.-]*$/;
// Signing in and out has its own route (/api/session) with its own rules.
const BLOCKED_FIRST_SEGMENTS = new Set(["auth"]);
// Big enough for the longest clinical note, small enough to stop abuse.
export const MAX_BODY_BYTES = 64 * 1024;
const DEVICE_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Message = { message: string };
const NOT_SIGNED_IN: Message = { message: "Not signed in." };
const REFUSED: Message = { message: "Request refused." };
const NOT_FOUND: Message = { message: "Not found." };
const TOO_LARGE: Message = { message: "That is too much to send at once." };
const UNAVAILABLE: Message = { message: "The service is unavailable. Please try again." };

// Patient data must never be stored by a browser or a middleman.
function reply(body: unknown, status: number) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

/** "/encounters/abc" from ["encounters", "abc"], or null if anything looks unsafe. */
export function backendPath(segments: string[]): string | null {
  if (segments.length === 0 || BLOCKED_FIRST_SEGMENTS.has(segments[0])) {
    return null;
  }
  if (!segments.every((segment) => SAFE_SEGMENT.test(segment))) {
    return null;
  }
  return `/${segments.join("/")}`;
}

export async function forwardToBackend(request: Request, segments: string[]): Promise<Response> {
  const isRead = request.method === "GET";
  // A page on another website must never be able to write as our signed-in user.
  if (!isRead && !isSameOrigin(request)) {
    return reply(REFUSED, 403);
  }

  const path = backendPath(segments);
  if (path === null) {
    return reply(NOT_FOUND, 404);
  }

  const token = await readSessionToken();
  if (!token) {
    return reply(NOT_SIGNED_IN, 401);
  }

  let body: string | undefined;
  if (!isRead) {
    body = await request.text();
    if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) {
      return reply(TOO_LARGE, 413);
    }
  }

  // The only browser headers passed on. Idempotency-Key lets the backend run a repeated
  // write once (offline outbox replays); the backend checks its format.
  const idempotencyKey = request.headers.get("idempotency-key");
  // X-Device-Id says which device a change came from (audit diary). Only a real UUID.
  const deviceId = request.headers.get("x-device-id");
  const validDeviceId = deviceId && DEVICE_ID.test(deviceId) ? deviceId : null;

  let answer: Response;
  try {
    const query = new URL(request.url).search;
    answer = await fetch(`${apiBase()}${path}${query}`, {
      method: request.method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
        ...(validDeviceId ? { "X-Device-Id": validDeviceId } : {}),
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    return reply(UNAVAILABLE, 502);
  }

  if (answer.status === 401) {
    await clearSession(); // the token expired or the account was switched off
    return reply(NOT_SIGNED_IN, 401);
  }
  if (answer.status >= 500) {
    return reply(UNAVAILABLE, 502); // never show a crash's details
  }

  // Our backend's own answers (data, or a 4xx message written for staff) pass through.
  const text = await answer.text();
  return new NextResponse(text, {
    status: answer.status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
