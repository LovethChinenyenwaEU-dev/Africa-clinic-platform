"use client";

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  LOGIN_MESSAGES,
  LoginError,
  confirmAppSetup,
  groupSecret,
  startAppSetup,
  verifyCode,
} from "./api";
import { mfaCodeSchema } from "./schemas";

/*
 * The second sign-in step for admins and billing (Week 11): the code from their
 * authenticator app, or the first-time set-up of that app. The challenge from the
 * password step is in an httpOnly cookie; these screens never see it.
 */

function messageFor(error: unknown): string {
  return error instanceof LoginError ? LOGIN_MESSAGES[error.kind] : LOGIN_MESSAGES.unavailable;
}

function isExpired(error: unknown): boolean {
  return error instanceof LoginError && error.kind === "expired";
}

/** One box for the 6-digit code (or a backup code), with its own checks. */
function CodeForm({
  label,
  hint,
  submitLabel,
  pending,
  failure,
  onCode,
}: {
  label: string;
  hint: string;
  submitLabel: string;
  pending: boolean;
  failure: string | null;
  onCode: (code: string) => void;
}) {
  const [code, setCode] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = mfaCodeSchema.safeParse(code);
    if (!parsed.success) {
      setProblem(parsed.error.issues[0]?.message ?? LOGIN_MESSAGES.wrong_code);
      return;
    }
    setProblem(null);
    onCode(parsed.data);
    setCode(""); // a code is used once: never leave it in the box
  }

  const shown = problem ?? failure;
  return (
    <form className="grid gap-3" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="mfa-code">{label}</label>
        <input
          id="mfa-code"
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          value={code}
          onChange={(event) => setCode(event.target.value)}
          aria-invalid={Boolean(shown)}
          aria-describedby="mfa-code-hint"
          className="font-mono text-lg tracking-[0.3em]"
        />
        <p id="mfa-code-hint" className="m-0 text-sm text-muted">
          {hint}
        </p>
      </div>
      {shown && (
        <p role="alert" className="error">
          {shown}
        </p>
      )}
      <button className="button" type="submit" disabled={pending}>
        {pending ? "Checking..." : submitLabel}
      </button>
    </form>
  );
}

/** Every sign-in after the first: the code the app shows now. */
export function VerifyStep({ onDone, onRestart }: { onDone: () => void; onRestart: () => void }) {
  const verify = useMutation({ mutationFn: verifyCode, onSuccess: onDone });

  return (
    <div className="card">
      <p className="eyebrow m-0">Second step</p>
      <h2 className="mb-0">Type the code from your authenticator app</h2>
      <CodeForm
        label="6-digit code"
        hint="Lost your phone? Type one of your backup codes instead, such as ABCD-EFGH."
        submitLabel="Sign in"
        pending={verify.isPending}
        failure={verify.isError ? messageFor(verify.error) : null}
        onCode={(code) => verify.mutate(code)}
      />
      {isExpired(verify.error) && <Restart onRestart={onRestart} />}
    </div>
  );
}

/** The first sign-in: add the app, prove it with a code, then keep the backup codes. */
export function SetupStep({
  onSignedIn,
  onRestart,
}: {
  onSignedIn: (backupCodes: string[]) => void;
  onRestart: () => void;
}) {
  const setup = useMutation({ mutationFn: startAppSetup });
  const confirm = useMutation({ mutationFn: confirmAppSetup, onSuccess: onSignedIn });

  return (
    <div className="card">
      <p className="eyebrow m-0">Second step, first time</p>
      <h2 className="mb-0">Set up your authenticator app</h2>
      <p className="m-0 text-sm">
        Your role looks after staff or money, so signing in needs a code from an app on your
        phone as well as your password. Install Google Authenticator, Microsoft Authenticator
        or a similar app first.
      </p>

      {!setup.data && (
        <button
          type="button"
          className="button"
          disabled={setup.isPending}
          onClick={() => setup.mutate()}
        >
          {setup.isPending ? "Making your key..." : "Show my set-up key"}
        </button>
      )}
      {setup.isError && (
        <p role="alert" className="error">
          {messageFor(setup.error)}
        </p>
      )}

      {setup.data && (
        <>
          <ol className="m-0 grid gap-2 pl-5 text-sm">
            <li>In the app, choose to add an account, then &ldquo;enter a setup key&rdquo;.</li>
            <li>
              Type this key (time-based), or on a phone{" "}
              <a href={setup.data.otpauth_uri} className="font-bold text-accent">
                open it in the app
              </a>
              :
            </li>
          </ol>
          <p
            className="m-0 rounded-lg bg-accent-soft p-3 text-center font-mono text-lg font-medium tracking-wider break-all text-accent-dark"
            aria-label="Your set-up key"
          >
            {groupSecret(setup.data.secret)}
          </p>
          <CodeForm
            label="Then type the 6-digit code the app shows"
            hint="This proves the app works. The code changes every 30 seconds."
            submitLabel="Finish set-up"
            pending={confirm.isPending}
            failure={confirm.isError ? messageFor(confirm.error) : null}
            onCode={(code) => confirm.mutate(code)}
          />
        </>
      )}
      {(isExpired(setup.error) || isExpired(confirm.error)) && <Restart onRestart={onRestart} />}
    </div>
  );
}

/** The backup codes, shown once. The person must say they kept them before going on. */
export function BackupCodes({ codes, onContinue }: { codes: string[]; onContinue: () => void }) {
  const [kept, setKept] = useState(false);

  return (
    <div className="card">
      <p className="eyebrow m-0">You are signed in</p>
      <h2 className="mb-0">Keep your backup codes</h2>
      <p className="m-0 text-sm">
        If you lose your phone, each code signs you in once. Write them down or print this
        page and keep them somewhere safe. They are shown only now.
      </p>
      <ul className="m-0 grid grid-cols-2 gap-2 p-0 font-mono text-base" aria-label="Backup codes">
        {codes.map((code) => (
          <li key={code} className="list-none rounded-md border border-line bg-[#fbfcf7] p-2 text-center">
            {code}
          </li>
        ))}
      </ul>
      <label className="flex items-center gap-2 font-normal">
        <input type="checkbox" checked={kept} onChange={(event) => setKept(event.target.checked)} className="min-h-0" />
        I have kept these codes somewhere safe
      </label>
      <button type="button" className="button" disabled={!kept} onClick={onContinue}>
        Continue
      </button>
    </div>
  );
}

function Restart({ onRestart }: { onRestart: () => void }) {
  return (
    <button type="button" className="button-secondary" onClick={onRestart}>
      Sign in again
    </button>
  );
}
