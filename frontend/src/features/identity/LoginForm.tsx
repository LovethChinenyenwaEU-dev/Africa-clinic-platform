"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { LOGIN_MESSAGES, LoginError, login } from "./api";
import { fieldErrorsFrom, type FieldErrors } from "./form-errors";
import { loginFormSchema } from "./schemas";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const signIn = useMutation({
    mutationFn: login,
    onSuccess: () => {
      router.replace("/");
      router.refresh();
    },
    onError: () => setPassword(""), // never leave a rejected password sitting in the box
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = loginFormSchema.safeParse({ email, password });
    if (!parsed.success) {
      setFieldErrors(fieldErrorsFrom(parsed.error));
      return;
    }
    setFieldErrors({});
    signIn.mutate(parsed.data);
  }

  let failure: string | null = null;
  if (signIn.error) {
    failure =
      signIn.error instanceof LoginError
        ? LOGIN_MESSAGES[signIn.error.kind]
        : LOGIN_MESSAGES.unavailable;
  }

  return (
    <form className="card" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? "email-error" : undefined}
        />
        {fieldErrors.email && (
          <p id="email-error" className="error">
            {fieldErrors.email}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby={fieldErrors.password ? "password-error" : undefined}
        />
        {fieldErrors.password && (
          <p id="password-error" className="error">
            {fieldErrors.password}
          </p>
        )}
      </div>

      {failure && (
        <p role="alert" className="error">
          {failure}
        </p>
      )}

      <button className="button" type="submit" disabled={signIn.isPending}>
        {signIn.isPending ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}