"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { useSync } from "@/features/sync/SyncProvider";
import { errorMessage } from "@/lib/api-client";

import {
  getPrescriptions,
  prescriptionRevisionWrite,
  prescriptionWrite,
  type PrescriptionDetails,
} from "./api";
import { ConflictChoice } from "./ConflictChoice";
import { ROUTE_LABELS } from "./labels";
import {
  EMPTY_PRESCRIPTION as EMPTY,
  describePrescription,
  prescriptionFromForm,
  type PrescriptionForm as Form,
} from "./prescribing";
import type { Prescription } from "./schemas";
import type { RecordContext } from "./VitalsPanel";

export function PrescriptionsPanel({
  encounter,
  nameOf,
  canPrescribe,
}: RecordContext & { canPrescribe: boolean }) {
  const queryClient = useQueryClient();
  const { queue } = useSync();
  const [showHistory, setShowHistory] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<Form>(EMPTY);
  const [problem, setProblem] = useState<string | null>(null);

  const key = ["prescriptions", encounter.id];
  const prescriptions = useQuery({
    queryKey: [...key, showHistory],
    queryFn: () => getPrescriptions(encounter.id, showHistory),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });

  const add = useMutation({
    mutationFn: (details: PrescriptionDetails) => queue(prescriptionWrite(encounter.id, details)),
    onSuccess: () => {
      setAdding(false);
      setForm(EMPTY);
      refresh();
    },
  });
  const change = useMutation({
    mutationFn: ({ row, status }: { row: Prescription; status: "stopped" | "entered_in_error" }) =>
      queue(prescriptionRevisionWrite(row, status)),
    onSuccess: refresh,
  });

  const isOpen = encounter.status === "open";
  const canChange = (row: Prescription) =>
    canPrescribe &&
    row.version_status === "current" &&
    row.clinical_status === "active" &&
    encounter.status !== "entered_in_error";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = prescriptionFromForm(form);
    if ("problem" in result) return setProblem(result.problem);
    setProblem(null);
    add.mutate(result);
  }

  const box = (field: keyof Form, label: string, placeholder = "") => (
    <div className="field">
      <label htmlFor={`rx-${field}`}>{label}</label>
      <input
        id={`rx-${field}`}
        autoComplete="off"
        placeholder={placeholder}
        value={form[field]}
        onChange={(event) => setForm({ ...form, [field]: event.target.value })}
      />
    </div>
  );

  return (
    <section aria-labelledby="prescriptions-heading" className="card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="prescriptions-heading" className="mb-0">
          Prescriptions
        </h2>
        <label className="flex items-center gap-2 text-sm font-normal">
          <input
            type="checkbox"
            checked={showHistory}
            onChange={(event) => setShowHistory(event.target.checked)}
          />
          Show earlier versions
        </label>
      </div>

      {prescriptions.isPending && <p>Loading prescriptions...</p>}
      {prescriptions.isError && (
        <p role="alert" className="error">
          {errorMessage(prescriptions.error)}
        </p>
      )}
      {prescriptions.data?.length === 0 && <p>Nothing prescribed in this visit.</p>}
      {prescriptions.data && prescriptions.data.length > 0 && (
        <ul className="grid gap-2">
          {prescriptions.data.map((row) => (
            <li
              key={row.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line pt-2"
            >
              <span
                className={
                  row.version_status === "superseded" || row.clinical_status !== "active"
                    ? "text-gray-600 line-through"
                    : "font-semibold"
                }
              >
                {describePrescription(row)}
              </span>
              {row.instructions && <span className="text-sm">({row.instructions})</span>}
              {row.clinical_status === "stopped" && (
                <span className="badge bg-gray-200 text-gray-800">Stopped</span>
              )}
              {row.clinical_status === "entered_in_error" && (
                <span className="badge bg-gray-200 text-gray-800">Written by mistake</span>
              )}
              {row.version_status === "superseded" && (
                <span className="badge bg-gray-200 text-gray-800">Earlier version</span>
              )}
              {row.synced_late && (
                <span className="badge bg-amber-100 text-amber-900">Synced late</span>
              )}
              <span className="text-sm">by {nameOf(row.recorded_by_id)}</span>
              {canChange(row) && (
                <span className="ml-auto flex flex-wrap gap-2">
                  <ConfirmAction
                    label="Stop"
                    question={`Stop ${row.medicine}?`}
                    pending={change.isPending}
                    onConfirm={() => change.mutate({ row, status: "stopped" })}
                  />
                  <ConfirmAction
                    label="Written by mistake"
                    question="Hide this prescription? It is kept in the history."
                    pending={change.isPending}
                    onConfirm={() => change.mutate({ row, status: "entered_in_error" })}
                  />
                </span>
              )}
              {row.version_status === "conflict" && (
                <ConflictChoice
                  kind="prescriptions"
                  id={row.id}
                  allowed={canPrescribe}
                  queryKey={key}
                  whoMayChoose="A doctor can choose which version to keep."
                />
              )}
            </li>
          ))}
        </ul>
      )}
      {change.isError && (
        <p role="alert" className="error">
          {errorMessage(change.error)}
        </p>
      )}

      {isOpen &&
        canPrescribe &&
        (adding ? (
          <form onSubmit={handleSubmit} noValidate className="grid gap-3 sm:grid-cols-3">
            {box("medicine", "Medicine", "Artemether-lumefantrine")}
            {box("strength", "Strength (optional)", "20/120 mg")}
            {box("dose", "Dose", "4 tablets")}
            <div className="field">
              <label htmlFor="rx-route">Route</label>
              <select
                id="rx-route"
                value={form.route}
                onChange={(event) => setForm({ ...form, route: event.target.value })}
              >
                {Object.entries(ROUTE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            {box("frequency", "How often", "twice daily")}
            {box("duration", "How long", "3 days")}
            <div className="field sm:col-span-3">
              <label htmlFor="rx-instructions">Instructions (optional)</label>
              <input
                id="rx-instructions"
                autoComplete="off"
                placeholder="Take with food"
                value={form.instructions}
                onChange={(event) => setForm({ ...form, instructions: event.target.value })}
              />
            </div>
            {(problem || add.isError) && (
              <p role="alert" className="error sm:col-span-3">
                {problem ?? errorMessage(add.error)}
              </p>
            )}
            <div className="flex gap-3 sm:col-span-3">
              <button className="button" type="submit" disabled={add.isPending}>
                {add.isPending ? "Saving..." : "Save prescription"}
              </button>
              <button className="button-secondary" type="button" onClick={() => setAdding(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div>
            <button className="button-secondary" type="button" onClick={() => setAdding(true)}>
              Prescribe
            </button>
          </div>
        ))}
      {!canPrescribe && isOpen && (
        <p className="text-sm">Only a doctor can prescribe. You can see what was prescribed.</p>
      )}
    </section>
  );
}
