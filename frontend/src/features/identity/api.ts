import { z } from "zod";

import { getDeviceId } from "@/lib/device";

import type { LoginForm } from "./schemas";

export type LoginFailure =
  | "wrong_login"
  | "invalid_form"
  | "refused"
  | "unavailable"
  | "wrong_code"
  | "expired"
  | "locked"
  | "already_set_up";

export class LoginError extends Error {
  constructor(readonly kind: LoginFailure) {
    super(kind);
  }
}

// The only wording a person ever sees. Nothing from the server is shown raw.
export const LOGIN_MESSAGES: Record<LoginFailure, string> = {
  wrong_login: "Invalid email or password.",
  invalid_form: "Enter your email and password.",
  refused: "Request refused. Reload the page and try again.",
  unavailable: "The service is unavailable. Please try again.",
  wrong_code: "That code is not right. Check your app and try again.",
  expired: "This step has expired. Sign in again with your password.",
  locked: "Too many wrong codes. Try again in 15 minutes.",
  already_set_up: "Your app is already set up. Sign in again and type its code.",
};

const SESSION_URL = "/api/session";
const MFA_URL = "/api/session/mfa";

/** What comes after the password: signed in, or the authenticator step (Week 11). */
export type LoginStep = "done" | "setup" | "verify";

const stepAnswerSchema = z.object({ mfa: z.enum(["setup", "verify"]).optional() });

async function send(url: string, body: unknown): Promise<Response> {
  try {
    return await fetch(url, {
      method: "POST",
      // This device's id goes with every sign-in step, to name it in "My devices".
      headers: { "Content-Type": "application/json", "X-Device-Id": getDeviceId() },
      body: JSON.stringify(body),
    });
  } catch {
    throw new LoginError("unavailable");
  }
}

export async function login(form: LoginForm): Promise<LoginStep> {
  const response = await send(SESSION_URL, form);

  if (response.ok) {
    const answer = stepAnswerSchema.safeParse(await response.json().catch(() => ({})));
    return answer.success && answer.data.mfa ? answer.data.mfa : "done";
  }
  if (response.status === 401) throw new LoginError("wrong_login");
  if (response.status === 422) throw new LoginError("invalid_form");
  if (response.status === 403) throw new LoginError("refused");
  throw new LoginError("unavailable");
}

// --- the authenticator step (admins and billing) ------------------------------------

function mfaFailure(response: Response, codeStep: boolean): LoginError {
  // Before a code is typed (set-up), a 401 can only mean the 5 minutes ran out.
  if (response.status === 401) return new LoginError(codeStep ? "wrong_code" : "expired");
  if (response.status === 429) return new LoginError("locked");
  if (response.status === 409) return new LoginError("already_set_up");
  if (response.status === 422) return new LoginError("wrong_code");
  if (response.status === 403) return new LoginError("refused");
  return new LoginError("unavailable");
}

const setupSchema = z.object({ secret: z.string().min(1), otpauth_uri: z.string() });
export type AppSetup = z.infer<typeof setupSchema>;

/** First time: the secret to add to the authenticator app. */
export async function startAppSetup(): Promise<AppSetup> {
  const response = await send(MFA_URL, { step: "setup" });
  if (!response.ok) throw mfaFailure(response, false);
  const parsed = setupSchema.safeParse(await response.json().catch(() => null));
  if (!parsed.success) throw new LoginError("unavailable");
  return parsed.data;
}

/** The first code proves the app works. Answers the backup codes, shown once. */
export async function confirmAppSetup(code: string): Promise<string[]> {
  const response = await send(MFA_URL, { step: "confirm", code });
  if (!response.ok) throw mfaFailure(response, true);
  const parsed = z
    .object({ backup_codes: z.array(z.string()) })
    .safeParse(await response.json().catch(() => null));
  if (!parsed.success) throw new LoginError("unavailable");
  return parsed.data.backup_codes;
}

/** The code from the app, or a backup code. */
export async function verifyCode(code: string): Promise<void> {
  const response = await send(MFA_URL, { step: "verify", code });
  if (!response.ok) throw mfaFailure(response, true);
}

/** Group a long secret in fours so a person can type it: "ABCD EFGH ...". */
export function groupSecret(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

export async function logout(): Promise<void> {
  const response = await fetch(SESSION_URL, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Could not sign out. Please try again.");
  }
}
