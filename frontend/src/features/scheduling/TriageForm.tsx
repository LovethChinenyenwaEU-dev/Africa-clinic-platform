"use client";

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { errorMessage } from "@/lib/api-client";

import { recordTriage } from "./api";
import {
  RED_FLAG_LABELS,
  TRIAGE_LABELS,
  TRIAGE_LEVELS,
  effectiveLevel,
  type TriageLevel,
} from "./labels";

/*
 * Doctors and nurses: how urgent is this patient, and are there danger signs?
 * Any danger sign makes it an emergency; the form says so before it is saved.
 */
export function TriageForm({
  appointmentId,
  patientName,
  current,
  onDone,
  onCancel,
}: {
  appointmentId: string;
  patientName: string;
  current: { level: string | null; redFlags: string[] };
  onDone: () => void;
  onCancel: () => void;
}) {
  const [level, setLevel] = useState<TriageLevel>(
    (TRIAGE_LEVELS as readonly string[]).includes(current.level ?? "")
      ? (current.level as TriageLevel)
      : "standard",
  );
  const [redFlags, setRedFlags] = useState<string[]>(current.redFlags);
  const save = useMutation({
    mutationFn: () => recordTriage(appointmentId, level, redFlags),
    onSuccess: onDone,
  });
  const saved = effectiveLevel(level, redFlags);

  function toggle(flag: string, on: boolean) {
    setRedFlags((flags) => (on ? [...flags, flag] : flags.filter((item) => item !== flag)));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="grid w-full gap-3 rounded border border-line p-3">
      <p className="font-semibold">Triage {patientName}</p>

      <fieldset className="grid gap-1">
        <legend className="text-sm font-semibold">Danger signs (tick any)</legend>
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

      <fieldset className="grid gap-1" disabled={redFlags.length > 0}>
        <legend className="text-sm font-semibold">How urgent</legend>
        <div className="flex flex-wrap gap-4">
          {TRIAGE_LEVELS.map((choice) => (
            <label key={choice} className="flex items-center gap-2 text-sm font-normal">
              <input
                type="radio"
                name={`triage-${appointmentId}`}
                checked={saved === choice}
                onChange={() => setLevel(choice)}
              />
              {TRIAGE_LABELS[choice]}
            </label>
          ))}
        </div>
      </fieldset>

      {redFlags.length > 0 && (
        <p role="alert" className="notice">
          A danger sign makes this an emergency. Tell a clinician now; do not wait for the
          queue.
        </p>
      )}
      {save.isError && (
        <p role="alert" className="error">
          {errorMessage(save.error)}
        </p>
      )}
      <div className="flex gap-3">
        <button className="button" type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving..." : `Save: ${TRIAGE_LABELS[saved]}`}
        </button>
        <button className="button-secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
