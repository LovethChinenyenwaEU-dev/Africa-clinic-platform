"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { useSync } from "@/features/sync/SyncProvider";
import { errorMessage } from "@/lib/api-client";

import {
  allergyRevisionWrite,
  allergyWrite,
  getAllergies,
  getProblems,
  problemRevisionWrite,
  problemWrite,
  type AllergyDetails,
  type ProblemDetails,
} from "./api";
import { ConflictChoice } from "./ConflictChoice";
import { CATEGORY_LABELS, SEVERITY_LABELS } from "./labels";
import type { Allergy, Problem } from "./schemas";
import type { RecordContext } from "./VitalsPanel";

// The patient's lists belong to the patient, so every visit sees and updates the same ones.

function allergyDetails(allergy: Allergy, clinical_status: string): AllergyDetails {
  return {
    substance: allergy.substance,
    reaction: allergy.reaction,
    severity: allergy.severity,
    clinical_status,
  };
}

function problemDetails(problem: Problem, clinical_status: string): ProblemDetails {
  return {
    description: problem.description,
    category: problem.category,
    code: problem.code,
    clinical_status,
    onset_date: problem.onset_date,
  };
}

export function AllergiesPanel({ encounter, nameOf }: RecordContext) {
  const queryClient = useQueryClient();
  const { queue } = useSync();
  const key = ["allergies", encounter.patient_id];
  const allergies = useQuery({ queryKey: key, queryFn: () => getAllergies(encounter.patient_id) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });

  const [form, setForm] = useState({ substance: "", reaction: "", severity: "unknown" });
  const [adding, setAdding] = useState(false);
  const add = useMutation({
    mutationFn: () =>
      queue(
        allergyWrite(encounter.id, {
          substance: form.substance,
          reaction: form.reaction.trim() || null,
          severity: form.severity,
          clinical_status: "active",
        }),
      ),
    onSuccess: () => {
      setAdding(false);
      setForm({ substance: "", reaction: "", severity: "unknown" });
      refresh();
    },
  });
  const revise = useMutation({
    mutationFn: ({ allergy, status }: { allergy: Allergy; status: string }) =>
      queue(allergyRevisionWrite(allergy.id, encounter.id, allergyDetails(allergy, status))),
    onSuccess: refresh,
  });

  const isOpen = encounter.status === "open";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    add.mutate();
  }

  return (
    <section aria-labelledby="allergies-heading" className="card">
      <h2 id="allergies-heading" className="mb-0">
        Allergies
      </h2>
      {allergies.isPending && <p>Loading allergies...</p>}
      {allergies.isError && (
        <p role="alert" className="error">
          {errorMessage(allergies.error)}
        </p>
      )}
      {/* "None recorded" is not "no known allergies": nobody has confirmed anything. */}
      {allergies.data?.length === 0 && (
        <p className="notice">No allergies recorded. Ask the patient before prescribing.</p>
      )}
      {allergies.data && allergies.data.length > 0 && (
        <ul className="grid gap-2">
          {allergies.data.map((allergy) => (
            <li
              key={allergy.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line pt-2"
            >
              <span className="font-semibold">{allergy.substance}</span>
              {allergy.reaction && <span>({allergy.reaction})</span>}
              <span className="badge bg-red-100 text-red-900">
                {SEVERITY_LABELS[allergy.severity] ?? allergy.severity}
              </span>
              {allergy.clinical_status === "inactive" && (
                <span className="badge bg-gray-200 text-gray-800">No longer active</span>
              )}
              <span className="text-sm">by {nameOf(allergy.recorded_by_id)}</span>
              {isOpen && allergy.version_status === "current" && (
                <span className="ml-auto flex flex-wrap gap-2">
                  {allergy.clinical_status === "active" && (
                    <ConfirmAction
                      label="No longer active"
                      question={`Mark ${allergy.substance} as no longer active?`}
                      pending={revise.isPending}
                      onConfirm={() => revise.mutate({ allergy, status: "inactive" })}
                    />
                  )}
                  <ConfirmAction
                    label="Recorded by mistake"
                    question="Hide this entry? It is kept in the history."
                    pending={revise.isPending}
                    onConfirm={() => revise.mutate({ allergy, status: "entered_in_error" })}
                  />
                </span>
              )}
              {allergy.version_status === "conflict" && (
                <ConflictChoice kind="allergies" id={allergy.id} allowed queryKey={key} />
              )}
            </li>
          ))}
        </ul>
      )}
      {revise.isError && (
        <p role="alert" className="error">
          {errorMessage(revise.error)}
        </p>
      )}

      {isOpen &&
        (adding ? (
          <form onSubmit={handleSubmit} noValidate className="grid gap-3 sm:grid-cols-3">
            <div className="field">
              <label htmlFor="allergy-substance">Substance</label>
              <input
                id="allergy-substance"
                value={form.substance}
                onChange={(event) => setForm({ ...form, substance: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="allergy-reaction">Reaction (optional)</label>
              <input
                id="allergy-reaction"
                value={form.reaction}
                onChange={(event) => setForm({ ...form, reaction: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="allergy-severity">Severity</label>
              <select
                id="allergy-severity"
                value={form.severity}
                onChange={(event) => setForm({ ...form, severity: event.target.value })}
              >
                {Object.entries(SEVERITY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            {add.isError && (
              <p role="alert" className="error sm:col-span-3">
                {errorMessage(add.error)}
              </p>
            )}
            <div className="flex gap-3 sm:col-span-3">
              <button className="button" type="submit" disabled={add.isPending}>
                {add.isPending ? "Saving..." : "Save allergy"}
              </button>
              <button className="button-secondary" type="button" onClick={() => setAdding(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div>
            <button className="button-secondary" type="button" onClick={() => setAdding(true)}>
              Add an allergy
            </button>
          </div>
        ))}
    </section>
  );
}

export function ProblemsPanel({ encounter, nameOf }: RecordContext) {
  const queryClient = useQueryClient();
  const { queue } = useSync();
  const key = ["problems", encounter.patient_id];
  const problems = useQuery({ queryKey: key, queryFn: () => getProblems(encounter.patient_id) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });

  const empty = { description: "", category: "encounter_diagnosis", code: "" };
  const [form, setForm] = useState(empty);
  const [adding, setAdding] = useState(false);
  const add = useMutation({
    mutationFn: () =>
      queue(
        problemWrite(encounter.id, {
          description: form.description,
          category: form.category,
          code: form.code.trim() || null,
          clinical_status: "active",
          onset_date: null,
        }),
      ),
    onSuccess: () => {
      setAdding(false);
      setForm(empty);
      refresh();
    },
  });
  const revise = useMutation({
    mutationFn: ({ problem, status }: { problem: Problem; status: string }) =>
      queue(problemRevisionWrite(problem.id, encounter.id, problemDetails(problem, status))),
    onSuccess: refresh,
  });

  const isOpen = encounter.status === "open";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    add.mutate();
  }

  return (
    <section aria-labelledby="problems-heading" className="card">
      <h2 id="problems-heading" className="mb-0">
        Problems and diagnoses
      </h2>
      {problems.isPending && <p>Loading problems...</p>}
      {problems.isError && (
        <p role="alert" className="error">
          {errorMessage(problems.error)}
        </p>
      )}
      {problems.data?.length === 0 && <p>No problems or diagnoses recorded.</p>}
      {problems.data && problems.data.length > 0 && (
        <ul className="grid gap-2">
          {problems.data.map((problem) => (
            <li
              key={problem.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line pt-2"
            >
              <span className="font-semibold">{problem.description}</span>
              {problem.code && <span className="font-mono text-sm">{problem.code}</span>}
              <span className="badge bg-blue-100 text-blue-900">
                {CATEGORY_LABELS[problem.category] ?? problem.category}
              </span>
              {problem.clinical_status === "resolved" && (
                <span className="badge bg-gray-200 text-gray-800">Resolved</span>
              )}
              <span className="text-sm">by {nameOf(problem.recorded_by_id)}</span>
              {isOpen && problem.version_status === "current" && (
                <span className="ml-auto flex flex-wrap gap-2">
                  {problem.clinical_status === "active" && (
                    <ConfirmAction
                      label="Resolved"
                      question={`Mark ${problem.description} as resolved?`}
                      pending={revise.isPending}
                      onConfirm={() => revise.mutate({ problem, status: "resolved" })}
                    />
                  )}
                  <ConfirmAction
                    label="Recorded by mistake"
                    question="Hide this entry? It is kept in the history."
                    pending={revise.isPending}
                    onConfirm={() => revise.mutate({ problem, status: "entered_in_error" })}
                  />
                </span>
              )}
              {problem.version_status === "conflict" && (
                <ConflictChoice kind="problems" id={problem.id} allowed queryKey={key} />
              )}
            </li>
          ))}
        </ul>
      )}
      {revise.isError && (
        <p role="alert" className="error">
          {errorMessage(revise.error)}
        </p>
      )}

      {isOpen &&
        (adding ? (
          <form onSubmit={handleSubmit} noValidate className="grid gap-3 sm:grid-cols-3">
            <div className="field sm:col-span-3">
              <label htmlFor="problem-description">Description</label>
              <input
                id="problem-description"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="problem-category">Type</label>
              <select
                id="problem-category"
                value={form.category}
                onChange={(event) => setForm({ ...form, category: event.target.value })}
              >
                {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="problem-code">ICD-10 code (optional)</label>
              <input
                id="problem-code"
                placeholder="B54"
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
              />
            </div>
            {add.isError && (
              <p role="alert" className="error sm:col-span-3">
                {errorMessage(add.error)}
              </p>
            )}
            <div className="flex gap-3 sm:col-span-3">
              <button className="button" type="submit" disabled={add.isPending}>
                {add.isPending ? "Saving..." : "Save"}
              </button>
              <button className="button-secondary" type="button" onClick={() => setAdding(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div>
            <button className="button-secondary" type="button" onClick={() => setAdding(true)}>
              Add a problem or diagnosis
            </button>
          </div>
        ))}
    </section>
  );
}
