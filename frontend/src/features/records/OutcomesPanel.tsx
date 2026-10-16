"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { VISIT_TYPE_LABELS } from "@/features/scheduling/labels";
import { useSync } from "@/features/sync/SyncProvider";
import { errorMessage } from "@/lib/api-client";
import { formatDate, todayInLagos } from "@/lib/format";

import {
  cancelReferral,
  followUpWrite,
  getFollowUps,
  getReferrals,
  referralWrite,
  type FollowUpDetails,
  type ReferralDetails,
} from "./api";
import { FOLLOW_UP_STATUS_LABELS, URGENCY_LABELS } from "./labels";
import type { RecordContext } from "./VitalsPanel";

/*
 * What happens after this consultation (FR-C5): when to be seen again, and any
 * referral to another clinic or specialist. Both are written through the device
 * outbox, so they work offline like vitals and notes.
 */
export function OutcomesPanel({ encounter, meId, nameOf }: RecordContext) {
  const isOpen = encounter.status === "open";
  return (
    <section aria-labelledby="outcomes-heading" className="card grid gap-4">
      <h2 id="outcomes-heading" className="mb-0">
        Follow-up and referral
      </h2>
      <FollowUps encounterId={encounter.id} isOpen={isOpen} />
      <Referrals
        encounterId={encounter.id}
        isOpen={isOpen}
        canCancel={(writer) =>
          encounter.status !== "entered_in_error" &&
          (writer === meId || encounter.clinician_id === meId)
        }
        nameOf={nameOf}
      />
    </section>
  );
}

function FollowUps({ encounterId, isOpen }: { encounterId: string; isOpen: boolean }) {
  const queryClient = useQueryClient();
  const { queue } = useSync();
  const key = ["follow-ups", encounterId];
  const followUps = useQuery({ queryKey: key, queryFn: () => getFollowUps(encounterId) });
  const empty: FollowUpDetails = { due_date: "", visit_type: "in_person", instructions: null };
  const [form, setForm] = useState(empty);
  const [problem, setProblem] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: (details: FollowUpDetails) => queue(followUpWrite(encounterId, details)),
    onSuccess: () => {
      setForm(empty);
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.due_date) return setProblem("Choose the date to be seen by.");
    setProblem(null);
    add.mutate({ ...form, instructions: form.instructions?.trim() || null });
  }

  return (
    <div className="grid gap-2">
      <h3 className="mb-0 text-base font-semibold">Follow-up</h3>
      {followUps.isError && <p className="error">{errorMessage(followUps.error)}</p>}
      {followUps.data?.length === 0 && <p className="text-sm">No follow-up planned.</p>}
      <ul className="grid gap-1">
        {followUps.data?.map((row) => (
          <li key={row.id} className="flex flex-wrap items-center gap-x-3 text-sm">
            <span className="font-semibold">By {formatDate(row.due_date)}</span>
            <span>{VISIT_TYPE_LABELS[row.visit_type] ?? row.visit_type}</span>
            <span className="badge bg-gray-200 text-gray-800">
              {FOLLOW_UP_STATUS_LABELS[row.status] ?? row.status}
            </span>
            {row.instructions && <span>({row.instructions})</span>}
          </li>
        ))}
      </ul>
      {isOpen && (
        <form onSubmit={handleSubmit} noValidate className="grid gap-3 sm:grid-cols-3">
          <div className="field">
            <label htmlFor="follow-up-date">See again by</label>
            <input
              id="follow-up-date"
              type="date"
              min={todayInLagos()}
              value={form.due_date}
              onChange={(event) => setForm({ ...form, due_date: event.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="follow-up-kind">Kind</label>
            <select
              id="follow-up-kind"
              value={form.visit_type}
              onChange={(event) =>
                setForm({
                  ...form,
                  visit_type: event.target.value as FollowUpDetails["visit_type"],
                })
              }
            >
              {Object.entries(VISIT_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="follow-up-instructions">For the clinician (optional)</label>
            <input
              id="follow-up-instructions"
              autoComplete="off"
              maxLength={500}
              placeholder="Repeat blood pressure"
              value={form.instructions ?? ""}
              onChange={(event) => setForm({ ...form, instructions: event.target.value })}
            />
          </div>
          {(problem || add.isError) && (
            <p role="alert" className="error sm:col-span-3">
              {problem ?? errorMessage(add.error)}
            </p>
          )}
          <div className="sm:col-span-3">
            <button className="button-secondary" type="submit" disabled={add.isPending}>
              Plan follow-up
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function Referrals({
  encounterId,
  isOpen,
  canCancel,
  nameOf,
}: {
  encounterId: string;
  isOpen: boolean;
  canCancel: (writerId: string) => boolean;
  nameOf: (staffId: string) => string;
}) {
  const queryClient = useQueryClient();
  const { queue } = useSync();
  const key = ["referrals", encounterId];
  const referrals = useQuery({ queryKey: key, queryFn: () => getReferrals(encounterId) });
  const empty: ReferralDetails = { to_name: "", specialty: null, urgency: "routine", reason: "" };
  const [form, setForm] = useState(empty);
  const [writing, setWriting] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });
  const add = useMutation({
    mutationFn: (details: ReferralDetails) => queue(referralWrite(encounterId, details)),
    onSuccess: () => {
      setForm(empty);
      setWriting(false);
      refresh();
    },
  });
  const cancel = useMutation({ mutationFn: cancelReferral, onSuccess: refresh });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.to_name.trim()) return setProblem("Who is the referral to?");
    if (!form.reason.trim()) return setProblem("Give the reason, and what you ask of them.");
    setProblem(null);
    add.mutate({ ...form, specialty: form.specialty?.trim() || null });
  }

  return (
    <div className="grid gap-2 border-t border-line pt-3">
      <h3 className="mb-0 text-base font-semibold">Referral</h3>
      {referrals.isError && <p className="error">{errorMessage(referrals.error)}</p>}
      {referrals.data?.length === 0 && <p className="text-sm">No referral written.</p>}
      <ul className="grid gap-2">
        {referrals.data?.map((row) => (
          <li key={row.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className={row.status === "cancelled" ? "line-through" : "font-semibold"}>
              To {row.to_name}
              {row.specialty ? ` (${row.specialty})` : ""}
            </span>
            <span className="badge bg-amber-100 text-amber-900">
              {URGENCY_LABELS[row.urgency] ?? row.urgency}
            </span>
            {row.status === "cancelled" && (
              <span className="badge bg-gray-200 text-gray-800">Cancelled</span>
            )}
            <span>by {nameOf(row.recorded_by_id)}</span>
            <span className="ml-auto flex flex-wrap gap-2">
              {row.status === "active" && (
                <Link href={`/referrals/${row.id}`} className="button-secondary">
                  Letter
                </Link>
              )}
              {row.status === "active" && canCancel(row.recorded_by_id) && (
                <ConfirmAction
                  label="Cancel"
                  question="Cancel this referral? It is kept, marked cancelled."
                  pending={cancel.isPending}
                  onConfirm={() => cancel.mutate(row.id)}
                />
              )}
            </span>
          </li>
        ))}
      </ul>
      {cancel.isError && <p className="error">{errorMessage(cancel.error)}</p>}
      {isOpen &&
        (writing ? (
          <form onSubmit={handleSubmit} noValidate className="grid gap-3 sm:grid-cols-3">
            <div className="field">
              <label htmlFor="referral-to">To (clinic or specialist)</label>
              <input
                id="referral-to"
                autoComplete="off"
                maxLength={200}
                value={form.to_name}
                onChange={(event) => setForm({ ...form, to_name: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="referral-specialty">Specialty (optional)</label>
              <input
                id="referral-specialty"
                autoComplete="off"
                maxLength={100}
                value={form.specialty ?? ""}
                onChange={(event) => setForm({ ...form, specialty: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="referral-urgency">Urgency</label>
              <select
                id="referral-urgency"
                value={form.urgency}
                onChange={(event) =>
                  setForm({ ...form, urgency: event.target.value as ReferralDetails["urgency"] })
                }
              >
                {Object.entries(URGENCY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field sm:col-span-3">
              <label htmlFor="referral-reason">Reason, and what you ask of them</label>
              <textarea
                id="referral-reason"
                rows={5}
                maxLength={2000}
                value={form.reason}
                onChange={(event) => setForm({ ...form, reason: event.target.value })}
              />
            </div>
            {(problem || add.isError) && (
              <p role="alert" className="error sm:col-span-3">
                {problem ?? errorMessage(add.error)}
              </p>
            )}
            <div className="flex gap-3 sm:col-span-3">
              <button className="button" type="submit" disabled={add.isPending}>
                Save referral
              </button>
              <button className="button-secondary" type="button" onClick={() => setWriting(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div>
            <button className="button-secondary" type="button" onClick={() => setWriting(true)}>
              Write a referral
            </button>
          </div>
        ))}
    </div>
  );
}
