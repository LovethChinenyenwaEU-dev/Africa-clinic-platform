"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Logo } from "@/components/brand/Logo";
import { errorMessage } from "@/lib/api-client";
import { todayInLagos } from "@/lib/format";

import { confirmCode, requestCode, type SignInDetails } from "./api";
import { patientHome } from "./paths";

/*
 * Patient sign-in: phone number and date of birth, then the 6-digit code sent by SMS.
 * Kept simple for a small phone screen on a slow network: two short steps, big boxes.
 */
export function PatientSignIn({ clinicId }: { clinicId: string }) {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [born, setBorn] = useState("");
  const [code, setCode] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const details: SignInDetails = { clinic_id: clinicId, phone, date_of_birth: born };

  const ask = useMutation({ mutationFn: () => requestCode(details) });
  const confirm = useMutation({
    mutationFn: () => confirmCode(details, code),
    onSuccess: () => router.replace(patientHome(clinicId)),
  });

  function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!phone.trim() || !born) return setProblem("Enter your phone number and date of birth.");
    setProblem(null);
    ask.mutate();
  }

  function handleConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code.trim())) return setProblem("Enter the 6-digit code from the SMS.");
    setProblem(null);
    confirm.mutate();
  }

  const sent = ask.data;

  return (
    <main className="mx-auto grid max-w-md gap-5 px-4 py-8">
      <Logo size="sm" tagline />
      <h1 className="mb-0">Your clinic record</h1>
      <p>
        Sign in with the phone number the clinic has for you. We send a code by SMS; no
        password needed.
      </p>

      {!sent ? (
        <form className="card grid gap-4" onSubmit={handleAsk} noValidate>
          <div className="field">
            <label htmlFor="patient-phone">Phone number</label>
            <input
              id="patient-phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="0803 123 4567"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="patient-born">Date of birth</label>
            <input
              id="patient-born"
              type="date"
              min="1900-01-01"
              max={todayInLagos()}
              value={born}
              onChange={(event) => setBorn(event.target.value)}
            />
          </div>
          {(problem || ask.isError) && (
            <p role="alert" className="error">
              {problem ?? errorMessage(ask.error)}
            </p>
          )}
          <button className="button" type="submit" disabled={ask.isPending}>
            {ask.isPending ? "Sending..." : "Send me a code"}
          </button>
        </form>
      ) : (
        <form className="card grid gap-4" onSubmit={handleConfirm} noValidate>
          <p role="status">{sent.message}</p>
          {sent.development_code && (
            <p className="notice">
              Development only (SMS is switched off): the code is {sent.development_code}
            </p>
          )}
          <div className="field">
            <label htmlFor="patient-code">Code from the SMS</label>
            <input
              id="patient-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </div>
          {(problem || confirm.isError) && (
            <p role="alert" className="error">
              {problem ?? errorMessage(confirm.error)}
            </p>
          )}
          <button className="button" type="submit" disabled={confirm.isPending}>
            {confirm.isPending ? "Checking..." : "Sign in"}
          </button>
          <button
            className="button-secondary"
            type="button"
            onClick={() => {
              ask.reset();
              setCode("");
            }}
          >
            Start again
          </button>
        </form>
      )}
      <p className="text-sm">
        Never share the code with anyone, not even clinic staff. Clinic staff will never ask
        for it.
      </p>
    </main>
  );
}
