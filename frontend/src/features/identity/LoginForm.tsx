"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { LOGIN_MESSAGES, LoginError, login, type LoginStep } from "./api";
import { fieldErrorsFrom, type FieldErrors } from "./form-errors";
import { BackupCodes, SetupStep, VerifyStep } from "./MfaSteps";
import { loginFormSchema } from "./schemas";

type Stage = "password" | "setup" | "verify" | { backupCodes: string[] };

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  // Admins and billing have a second step after the password (Week 11).
  const [stage, setStage] = useState<Stage>("password");

  function enter() {
    router.replace("/");
    router.refresh();
  }

  const signIn = useMutation({
    mutationFn: login,
    onSuccess: (step: LoginStep) => {
      setPassword(""); // the password is done with either way
      if (step === "done") enter();
      else setStage(step);
    },
    onError: () => setPassword(""), // never leave a rejected password sitting in the box
  });

  // The 5-minute step ran out: back to the password.
  function restart() {
    setStage("password");
    signIn.reset();
  }

  if (stage === "verify") {
    return <VerifyStep onDone={enter} onRestart={restart} />;
  }
  if (stage === "setup") {
    return (
      <SetupStep onSignedIn={(backupCodes) => setStage({ backupCodes })} onRestart={restart} />
    );
  }
  if (typeof stage === "object") {
    return <BackupCodes codes={stage.backupCodes} onContinue={enter} />;
  }

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