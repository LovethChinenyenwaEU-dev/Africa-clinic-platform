import { NextResponse } from "next/server";
import { z } from "zod";

import {
  mfaCodeSchema,
  mfaConfirmedSchema,
  mfaSetupSchema,
  tokenResponseSchema,
} from "@/features/identity/schemas";
import { BackendRejectedError, callBackend } from "@/lib/server/backend";
import { isSameOrigin } from "@/lib/server/origin";
import { challengeSession, writeSessionToken } from "@/lib/server/session";
import { signInHeaders } from "@/lib/server/sign-in-headers";

/*
 * The second sign-in step for admins and billing (Week 11). The challenge from the
 * password step lives in an httpOnly cookie; this route hands it to the backend with
 * the person's code. On success it swaps the challenge for the normal session cookie.
 *
 *   { step: "setup" }                 -> the secret to add to the authenticator app
 *   { step: "confirm", code: "..." }  -> signed in, plus the backup codes (shown once)
 *   { step: "verify",  code: "..." }  -> signed in
 */

type Message = { message: string };

const REFUSED: Message = { message: "Request refused." };
const EXPIRED: Message = { message: "This step has expired. Sign in again." };
const WRONG_CODE: Message = { message: "That code is not right. Check your app and try again." };
const LOCKED: Message = { message: "Too many wrong codes. Try again in 15 minutes." };
const ALREADY: Message = { message: "Your app is already set up. Sign in again and type its code." };
const BAD_FORM: Message = { message: "Type the 6-digit code from your app." };
const UNAVAILABLE: Message = { message: "The service is unavailable. Please try again." };

const bodySchema = z.discriminatedUnion("step", [
  z.object({ step: z.literal("setup") }),
  z.object({ step: z.literal("confirm"), code: mfaCodeSchema }),
  z.object({ step: z.literal("verify"), code: mfaCodeSchema }),
]);

function reply(body: unknown, status = 200) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

function failure(error: unknown) {
  if (error instanceof BackendRejectedError) {
    if (error.status === 401) return reply(WRONG_CODE, 401);
    if (error.status === 429) return reply(LOCKED, 429);
    if (error.status === 409) return reply(ALREADY, 409);
    if (error.status === 422) return reply(BAD_FORM, 422);
  }
  return reply(UNAVAILABLE, 502);
}

// The device details go with the steps that sign a person in, to name the new sign-in.
function post(body: unknown, request: Request): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json", ...signInHeaders(request) },
    body: JSON.stringify(body),
  };
}

export async function POST(request: Request) {
  if (!isSameOrigin(request)) {
    return reply(REFUSED, 403);
  }
  const challenge = await challengeSession.read();
  if (!challenge) {
    return reply(EXPIRED, 401); // more than 5 minutes since the password, or never given
  }
  const form = bodySchema.safeParse(await request.json().catch(() => null));
  if (!form.success) {
    return reply(BAD_FORM, 422);
  }

  try {
    if (form.data.step === "setup") {
      const setup = await callBackend(
        "/auth/mfa/setup",
        mfaSetupSchema,
        post({ challenge_token: challenge }, request),
      );
      return reply(setup); // the secret must reach the person: they add it to their app
    }
    if (form.data.step === "confirm") {
      const done = await callBackend(
        "/auth/mfa/confirm",
        mfaConfirmedSchema,
        post({ challenge_token: challenge, code: form.data.code }, request),
      );
      await writeSessionToken(done.access_token);
      await challengeSession.clear();
      return reply({ ok: true, backup_codes: done.backup_codes });
    }
    const token = await callBackend(
      "/auth/mfa/verify",
      tokenResponseSchema,
      post({ challenge_token: challenge, code: form.data.code }, request),
    );
    await writeSessionToken(token.access_token);
    await challengeSession.clear();
    return reply({ ok: true });
  } catch (error) {
    return failure(error);
  }
}
