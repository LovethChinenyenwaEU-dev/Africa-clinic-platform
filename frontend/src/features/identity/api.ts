import type { LoginForm } from "./schemas";

export type LoginFailure = "wrong_login" | "invalid_form" | "refused" | "unavailable";

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
};

const SESSION_URL = "/api/session";

export async function login(form: LoginForm): Promise<void> {
  let response: Response;
  try {
    response = await fetch(SESSION_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
  } catch {
    throw new LoginError("unavailable");
  }

  if (response.ok) return;
  if (response.status === 401) throw new LoginError("wrong_login");
  if (response.status === 422) throw new LoginError("invalid_form");
  if (response.status === 403) throw new LoginError("refused");
  throw new LoginError("unavailable");
}

export async function logout(): Promise<void> {
  const response = await fetch(SESSION_URL, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Could not sign out. Please try again.");
  }
}