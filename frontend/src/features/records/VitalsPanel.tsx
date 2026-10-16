"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { errorMessage } from "@/lib/api-client";
import { formatTime } from "@/lib/format";

import { correctVitals, getVitals, recordVitals, type Readings } from "./api";
import { READING_LABELS } from "./labels";
import {
  EMPTY_READINGS,
  describeVitals,
  formFromVitals,
  readingsFromForm,
  type ReadingsForm,
} from "./readings";
import { READING_FIELDS, type Encounter, type Vitals } from "./schemas";

export type RecordContext = {
  encounter: Encounter;
  meId: string;
  nameOf: (staffId: string) => string;
};

function VitalsForm({
  initial,
  submitLabel,
  pending,
  onSubmit,
  onCancel,
}: {
  initial: ReadingsForm;
  submitLabel: string;
  pending: boolean;
  onSubmit: (readings: Readings) => void;
  onCancel?: () => void;
}) {
  const [form, setForm] = useState(initial);
  const [problem, setProblem] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = readingsFromForm(form);
    if ("problem" in result) {
      setProblem(result.problem);
      return;
    }
    setProblem(null);
    onSubmit(result.readings);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="grid gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {READING_FIELDS.map((field) => {
          const { label, unit } = READING_LABELS[field];
          const id = `${submitLabel}-${field}`.replace(/\s+/g, "-");
          return (
            <div key={field} className="field">
              <label htmlFor={id}>
                {label} <span className="font-normal">({unit})</span>
              </label>
              <input
                id={id}
                inputMode="decimal"
                autoComplete="off"
                value={form[field]}
                onChange={(event) => setForm({ ...form, [field]: event.target.value })}
              />
            </div>
          );
        })}
      </div>
      {problem && <p className="error">{problem}</p>}
      <div className="flex gap-3">
        <button className="button" type="submit" disabled={pending}>
          {pending ? "Saving..." : submitLabel}
        </button>
        {onCancel && (
          <button className="button-secondary" type="button" onClick={onCancel} disabled={pending}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

export function VitalsPanel({ encounter, meId, nameOf }: RecordContext) {
  const queryClient = useQueryClient();
  const [showHistory, setShowHistory] = useState(false);
  const [adding, setAdding] = useState(false);
  const [correcting, setCorrecting] = useState<Vitals | null>(null);

  const vitals = useQuery({
    queryKey: ["vitals", encounter.id, showHistory],
    queryFn: () => getVitals(encounter.id, showHistory),
  });
  const done = () => {
    setAdding(false);
    setCorrecting(null);
    void queryClient.invalidateQueries({ queryKey: ["vitals", encounter.id] });
  };
  const add = useMutation({
    mutationFn: (readings: Readings) => recordVitals(encounter.id, readings),
    onSuccess: done,
  });
  const correct = useMutation({
    mutationFn: ({ id, readings }: { id: string; readings: Readings }) =>
      correctVitals(id, readings),
    onSuccess: done,
  });

  const isOpen = encounter.status === "open";
  const canCorrect = (set: Vitals) =>
    set.status === "current" &&
    encounter.status !== "entered_in_error" &&
    (set.recorded_by_id === meId || encounter.clinician_id === meId);
  const failure = add.error ?? correct.error;

  return (
    <section aria-labelledby="vitals-heading" className="card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="vitals-heading" className="mb-0">
          Vitals
        </h2>
        <label className="flex items-center gap-2 text-sm font-normal">
          <input
            type="checkbox"
            checked={showHistory}
            onChange={(event) => setShowHistory(event.target.checked)}
          />
          Show corrected versions
        </label>
      </div>

      {vitals.isPending && <p>Loading vitals...</p>}
      {vitals.isError && (
        <p role="alert" className="error">
          {errorMessage(vitals.error)}
        </p>
      )}
      {vitals.data?.length === 0 && <p>No vitals recorded yet.</p>}
      {vitals.data && vitals.data.length > 0 && (
        <ul className="grid gap-2">
          {vitals.data.map((set) => (
            <li key={set.id} className="grid gap-1 border-t border-line pt-2">
              {correcting?.id === set.id ? (
                <VitalsForm
                  initial={formFromVitals(set)}
                  submitLabel="Save correction"
                  pending={correct.isPending}
                  onSubmit={(readings) => correct.mutate({ id: set.id, readings })}
                  onCancel={() => setCorrecting(null)}
                />
              ) : (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-mono">{formatTime(set.measured_at)}</span>
                  <span className={set.status === "superseded" ? "line-through" : ""}>
                    {describeVitals(set)}
                  </span>
                  {set.status === "superseded" && (
                    <span className="badge bg-gray-200 text-gray-800">Corrected later</span>
                  )}
                  {set.replaces_id && set.status === "current" && (
                    <span className="badge bg-blue-100 text-blue-900">Correction</span>
                  )}
                  {set.synced_late && (
                    <span
                      className="badge bg-amber-100 text-amber-900"
                      title="Taken before sign-off on a device that was offline; it arrived afterwards."
                    >
                      Synced late
                    </span>
                  )}
                  <span className="text-sm">by {nameOf(set.recorded_by_id)}</span>
                  {canCorrect(set) && (
                    <button
                      type="button"
                      className="button-secondary ml-auto"
                      onClick={() => setCorrecting(set)}
                    >
                      Correct
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {failure && (
        <p role="alert" className="error">
          {errorMessage(failure)}
        </p>
      )}

      {isOpen &&
        !correcting &&
        (adding ? (
          <VitalsForm
            initial={EMPTY_READINGS}
            submitLabel="Save vitals"
            pending={add.isPending}
            onSubmit={(readings) => add.mutate(readings)}
            onCancel={() => setAdding(false)}
          />
        ) : (
          <div>
            <button className="button" type="button" onClick={() => setAdding(true)}>
              Record vitals
            </button>
          </div>
        ))}
    </section>
  );
}
