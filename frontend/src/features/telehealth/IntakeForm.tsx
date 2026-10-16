"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { RED_FLAG_LABELS } from "@/features/scheduling/labels";
import { errorMessage } from "@/lib/api-client";

import { getTeleconsultStatus, submitIntake } from "./api";

const MAX_REASON = 500;

/*
 * Before a remote visit (often on the phone): consent, the reason, and the danger-sign
 * questions. Ask every question out loud; any "yes" means in-person care.
 */
export function IntakeForm({
  appointmentId,
  patientId,
  patientName,
  onDone,
  onCancel,
}: {
  appointmentId: string;
  patientId: string;
  patientName: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [redFlags, setRedFlags] = useState<string[]>([]);
  const [problem, setProblem] = useState<string | null>(null);

  const status = useQuery({
    queryKey: ["teleconsult-status", appointmentId],
    queryFn: () => getTeleconsultStatus(appointmentId),
  });
  const save = useMutation({
    mutationFn: () => submitIntake(appointmentId, reason, redFlags),
    onSuccess: (result) => {
      if (result.outcome === "ready") onDone();
    },
  });

  function toggle(flag: string, on: boolean) {
    setRedFlags((flags) => (on ? [...flags, flag] : flags.filter((item) => item !== flag)));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason.trim()) return setProblem("Ask why the patient wants the visit.");
    setProblem(null);
    save.mutate();
  }

  const result = save.data;

  return (
    <div className="grid w-full gap-3 rounded border border-line p-3">
      <p className="font-semibold">Remote visit intake: {patientName}</p>

      {status.data && !status.data.consented && (
        <p role="alert" className="notice">
          {patientName} has not agreed to remote care yet. Read the wording and record their
          consent (purpose: teleconsult) on{" "}
          <Link href={`/patients/${patientId}`} target="_blank" className="text-accent underline">
            the patient&apos;s page
          </Link>{" "}
          (opens in a new tab), then{" "}
          <button
            type="button"
            className="text-accent underline"
            onClick={() => void status.refetch()}
          >
            check again
          </button>
          .
        </p>
      )}

      {result?.outcome === "escalated" ? (
        <div role="alert" className="grid gap-2 rounded border border-red-300 bg-red-50 p-3">
          <p className="font-semibold text-red-900">Not safe for a remote visit</p>
          <p>{result.advice}</p>
          <p className="text-sm">
            This has been recorded. Cancel this remote visit and book the patient in person.
          </p>
          <div>
            <button className="button-secondary" type="button" onClick={onCancel}>
              Close
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="grid gap-3" noValidate>
          <div className="field">
            <label htmlFor={`intake-reason-${appointmentId}`}>Reason for the visit</label>
            <textarea
              id={`intake-reason-${appointmentId}`}
              rows={3}
              maxLength={MAX_REASON}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
          <fieldset className="grid gap-1">
            <legend className="text-sm font-semibold">
              Ask each one. Does the patient have any of these now?
            </legend>
            <div className="grid gap-1 sm:grid-cols-2">
              {Object.entries(RED_FLAG_LABELS).map(([flag, label]) => (
                <label key={flag} className="flex items-center gap-2 text-sm font-normal">
                  <input
                    type="checkbox"
                    checked={redFlags.includes(flag)}
                    onChange={(event) => toggle(flag, event.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          {redFlags.length > 0 && (
            <p className="notice">
              A danger sign means this patient must be seen in person. Saving records the
              advice; the remote visit will not go ahead.
            </p>
          )}
          {(problem || save.isError) && (
            <p role="alert" className="error">
              {problem ?? errorMessage(save.error)}
            </p>
          )}
          <div className="flex gap-3">
            <button
              className="button"
              type="submit"
              disabled={save.isPending || status.data?.consented === false}
            >
              {save.isPending
                ? "Saving..."
                : redFlags.length > 0
                  ? "Save: send to in-person care"
                  : "Save: join the remote waiting room"}
            </button>
            <button className="button-secondary" type="button" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
