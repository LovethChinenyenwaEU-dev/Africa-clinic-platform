import { NextResponse } from "next/server";
import { z } from "zod";

import { loginFormSchema, loginResponseSchema, meSchema } from "@/features/identity/schemas";
import {
  BackendRejectedError,
  callBackend,
} from "@/lib/server/backend";
import { isSameOrigin } from "@/lib/server/origin";
import {
  challengeSession,
  clearSession,
  readSessionToken,
  writeSessionToken,
} from "@/lib/server/session";
import { signInHeaders } from "@/lib/server/sign-in-headers";

type Message = { message: string };

const NOT_SIGNED_IN: Message = { message: "Not signed in." };
const WRONG_LOGIN: Message = { message: "Invalid email or password." };
const BAD_FORM: Message = { message: "Enter your email and password." };
const REFUSED: Message = { message: "Request refused." };
const UNAVAILABLE: Message = { message: "The service is unavailable. Please try again." };

// Personal answers must never be stored by a browser or a middleman.
function reply(body: unknown, status = 200) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

function backendSaidNo(error: unknown): boolean {
  return error instanceof BackendRejectedError && error.status === 401;
}

// Log in.
export async function POST(request: Request) {
  if (!isSameOrigin(request)) {
    return reply(REFUSED, 403);
  }

  const form = loginFormSchema.safeParse(await request.json().catch(() => null));
  if (!form.success) {
    return reply(BAD_FORM, 422);
  }

  try {
    const answer = await callBackend("/auth/login", loginResponseSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...signInHeaders(request) },
      body: JSON.stringify(form.data),
    });
    if ("access_token" in answer) {
      await writeSessionToken(answer.access_token);
      return reply({ ok: true });
    }
    // Admins and billing: the code step comes next. The challenge stays in its own
    // httpOnly cookie; the page only learns which step (setup or verify).
    await challengeSession.write(answer.challenge_token);
    return reply({ mfa: answer.mfa });
  } catch (error) {
    return backendSaidNo(error) ? reply(WRONG_LOGIN, 401) : reply(UNAVAILABLE, 502);
  }
}

// Who am I?
export async function GET() {
  const token = await readSessionToken();
  if (!token) {
    return reply(NOT_SIGNED_IN, 401);
  }

  try {
    const me = await callBackend("/auth/me", meSchema, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return reply(me);
  } catch (error) {
    if (backendSaidNo(error)) {
      await clearSession(); // an expired or switched-off session is removed
      return reply(NOT_SIGNED_IN, 401);
    }
    return reply(UNAVAILABLE, 502);
  }
}

const signedOutSchema = z.object({ signed_out: z.literal(true) });

// Log out. The backend ends this device's sign-in first, so a copy of the token stops
// working at once (Week 11). The cookie is cleared even if the backend cannot be reached.
export async function DELETE(request: Request) {
  if (!isSameOrigin(request)) {
    return reply(REFUSED, 403);
  }
  const token = await readSessionToken();
  if (token) {
    await callBackend("/auth/logout", signedOutSchema, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {}); // already ended or expired: nothing more to do
  }
  await clearSession();
  return reply({ ok: true });
}