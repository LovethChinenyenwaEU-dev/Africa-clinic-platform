"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import {
  approveSummary,
  editSummary,
  getFollowUps,
  getPrescriptions,
  getProblems,
  getReferrals,
  getSummaries,
  startSummary,
  withdrawSummary,
} from "./api";
import type { Summary } from "./schemas";
import { draftFromVisit } from "./summarize";
import type { RecordContext } from "./VitalsPanel";

const MAX_SUMMARY = 4000;

/*
 * The patient's summary of this visit (FR-R4). A clinician drafts it in plain words;
 * the clinician who opened the encounter approves it after sign-off. Approved, it
 * never changes and the patient may read it (their own page, Week 9 Step 8).
 */
export function SummaryPanel({ encounter, meId, nameOf }: RecordContext) {
  const queryClient = useQueryClient();
  const key = ["summaries", encounter.id];
  const summaries = useQuery({ queryKey: key, queryFn: () => getSummaries(encounter.id) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);

  const current = summaries.data?.find((row) => row.status !== "withdrawn") ?? null;
  const withdrawn = summaries.data?.filter((row) => row.status === "withdrawn") ?? [];
  const isOwner = encounter.clinician_id === meId;
  const usable = encounter.status !== "entered_in_error";

  const save = useMutation({
    mutationFn: () => (current ? editSummary(current.id, text) : startSummary(encounter.id, text)),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });
  const approve = useMutation({ mutationFn: approveSummary, onSuccess: refresh });
  const withdraw = useMutation({ mutationFn: withdrawSummary, onSuccess: refresh });

  // "Start from this visit": read what was recorded and write a first draft.
  const prefill = useMutation({
    mutationFn: async () => {
      const [problems, prescriptions, followUps, referrals] = await Promise.all([
        getProblems(encounter.patient_id),
        getPrescriptions(encounter.id),
        getFollowUps(encounter.id),
        getReferrals(encounter.id),
      ]);
      return draftFromVisit({
        visitDay: encounter.opened_at,
        encounterId: encounter.id,
        problems,
        prescriptions,
        followUps,
        referrals,
      });
    },
    onSuccess: setText,
  });

  function startEditing(from: Summary | null) {
    setText(from?.body ?? "");
    setEditing(true);
  }

  const failure = save.error ?? approve.error ?? withdraw.error ?? prefill.error;

  return (
    <section aria-labelledby="summary-heading" className="card grid gap-3">
      <h2 id="summary-heading" className="mb-0">
        Summary for the patient
      </h2>
      {summaries.isError && <p className="error">{errorMessage(summaries.error)}</p>}

      {current && !editing && (
        <div className="grid gap-2">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            {current.status === "approved" ? (
              <span className="badge bg-green-100 text-green-900">
                Approved {current.approved_at ? formatDateTime(current.approved_at) : ""}: the
                patient can read it
              </span>
            ) : (
              <span className="badge bg-amber-100 text-amber-900">
                Draft: the patient cannot see it yet
              </span>
            )}
            <span>drafted by {nameOf(current.drafted_by_id)}</span>
          </p>
          <p className="whitespace-pre-wrap rounded border border-line p-3">{current.body}</p>
          <div className="flex flex-wrap gap-2">
            {current.status === "draft" && current.drafted_by_id === meId && usable && (
              <button className="button-secondary" type="button" onClick={() => startEditing(current)}>
                Edit draft
              </button>
            )}
            {current.status === "draft" && isOwner && usable && (
              encounter.status === "closed" ? (
                <ConfirmAction
                  label="Approve for the patient"
                  question="Approve? The patient will be able to read it, and it cannot be changed afterwards."
                  quiet={false}
                  pending={approve.isPending}
                  onConfirm={() => approve.mutate(current.id)}
                />
              ) : (
                <span className="text-sm">Sign off the encounter, then approve the summary.</span>
              )
            )}
            {current.status === "approved" && isOwner && (
              <ConfirmAction
                label="Withdraw"
                question="Withdraw this summary? The patient will no longer see it; it is kept, and you can write a new one."
                pending={withdraw.isPending}
                onConfirm={() => withdraw.mutate(current.id)}
              />
            )}
          </div>
          {current.status === "draft" && !isOwner && (
            <p className="text-sm">
              {nameOf(encounter.clinician_id)} approves it after signing off the encounter.
            </p>
          )}
        </div>
      )}

      {!current && !editing && usable && (
        <div>
          <button className="button-secondary" type="button" onClick={() => startEditing(null)}>
            Write a summary
          </button>
        </div>
      )}

      {editing && (
        <div className="grid gap-2">
          <div className="flex flex-wrap items-center gap-3">
            <button
              className="button-secondary"
              type="button"
              disabled={prefill.isPending}
              onClick={() => prefill.mutate()}
            >
              {prefill.isPending ? "Reading the record..." : "Start from this visit"}
            </button>
            <span className="text-sm">
              Fills in diagnoses, medicines and next steps. Read it and use plain words.
            </span>
          </div>
          <label htmlFor="summary-text" className="sr-only">
            Summary for the patient
          </label>
          <textarea
            id="summary-text"
            rows={12}
            maxLength={MAX_SUMMARY}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div className="flex gap-3">
            <button
              className="button"
              type="button"
              disabled={save.isPending || !text.trim()}
              onClick={() => save.mutate()}
            >
              {save.isPending ? "Saving..." : "Save draft"}
            </button>
            <button className="button-secondary" type="button" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {failure && (
        <p role="alert" className="error">
          {errorMessage(failure)}
        </p>
      )}

      {withdrawn.length > 0 && (
        <details className="text-sm">
          <summary>Withdrawn summaries ({withdrawn.length})</summary>
          <ul className="grid gap-2 pt-2">
            {withdrawn.map((row) => (
              <li key={row.id} className="whitespace-pre-wrap text-gray-600 line-through">
                {row.body}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
