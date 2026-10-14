"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { openRecord, startVisit } from "@/features/records/api";
import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { formatTime, todayInLagos, waitedFor } from "@/lib/format";

import {
  changeVisit,
  getBranches,
  getClinicians,
  getDayList,
  getQueue,
  type VisitAction,
} from "./api";
import { KIND_LABELS, STATUS_LABELS, STATUS_STYLES } from "./labels";
import type { Clinician, DayEntry } from "./schemas";
import { BookVisitForm, WalkInForm } from "./VisitForms";

// Each refresh is one diary line, so once a minute (and only while the screen is
// visible) is the balance between a live waiting room and a readable diary.
const REFRESH_MS = 60_000;
const BRANCH_KEY = "clinic.queue.branch"; // remembered on this device only

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : API_MESSAGES.unavailable;
}

function rememberedBranch(): string | null {
  try {
    return window.localStorage.getItem(BRANCH_KEY);
  } catch {
    return null; // private browsing or storage switched off: just ask again
  }
}

function rememberBranch(branchId: string) {
  try {
    window.localStorage.setItem(BRANCH_KEY, branchId);
  } catch {
    // Not being remembered is fine.
  }
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${STATUS_STYLES[status] ?? "bg-gray-200 text-gray-800"}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function clinicianName(clinicians: Clinician[], id: string | null): string {
  if (!id) return "Any clinician";
  return clinicians.find((person) => person.id === id)?.full_name ?? "A clinician";
}

type ActionButton = {
  action: VisitAction;
  label: string;
  // Final moves cannot be undone in the backend, so they ask "are you sure?" first.
  confirm: string | null;
};

// Which buttons a visit offers, by its status. The backend still checks every move.
const ACTIONS: Record<string, ActionButton[]> = {
  booked: [
    { action: "check-in", label: "Check in", confirm: null },
    { action: "no-show", label: "Did not come", confirm: "Mark as did not come?" },
    { action: "cancel", label: "Cancel", confirm: "Cancel this visit?" },
  ],
  waiting: [{ action: "cancel", label: "Cancel", confirm: "Cancel this visit?" }],
};

export function QueueBoard({ canConsult }: { canConsult: boolean }) {
  const queryClient = useQueryClient();
  const router = useRouter();

  // Doctors and nurses: start the visit (or reopen its record) and go to the encounter.
  const begin = useMutation({
    mutationFn: (entry: DayEntry) =>
      entry.status === "waiting"
        ? startVisit(entry.appointment_id, entry.patient_id)
        : openRecord(entry.appointment_id, entry.patient_id),
    onSuccess: (encounter) => router.push(`/encounters/${encounter.id}`),
  });
  const [branchId, setBranchId] = useState<string | null>(null);
  const [day, setDay] = useState(todayInLagos);
  const [form, setForm] = useState<"none" | "walk-in" | "book">("none");

  const branches = useQuery({ queryKey: ["branches"], queryFn: getBranches });
  const clinicians = useQuery({ queryKey: ["clinicians"], queryFn: getClinicians });

  // Choose the remembered branch, or the first one, once the list arrives.
  useEffect(() => {
    if (branchId || !branches.data?.length) return;
    const saved = rememberedBranch();
    const known = branches.data.some((branch) => branch.id === saved);
    setBranchId(known && saved ? saved : branches.data[0].id);
  }, [branches.data, branchId]);

  const queue = useQuery({
    queryKey: ["queue", branchId],
    queryFn: () => getQueue(branchId ?? ""),
    enabled: branchId !== null,
    refetchInterval: REFRESH_MS,
  });
  const dayList = useQuery({
    queryKey: ["day-list", branchId, day],
    queryFn: () => getDayList(branchId ?? "", day),
    enabled: branchId !== null,
    refetchInterval: day === todayInLagos() ? REFRESH_MS : false,
  });

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["queue", branchId] });
    void queryClient.invalidateQueries({ queryKey: ["day-list", branchId] });
  }

  // The visit and final move waiting for "Yes", if any.
  const [confirming, setConfirming] = useState<{ id: string; button: ActionButton } | null>(null);

  const change = useMutation({
    mutationFn: ({ entry, action }: { entry: DayEntry; action: VisitAction }) =>
      changeVisit(entry.appointment_id, action),
    onSuccess: refresh,
    onSettled: () => setConfirming(null),
  });

  function formDone() {
    setForm("none");
    refresh();
  }

  if (branches.isPending) return <p>Loading...</p>;
  if (branches.isError) {
    return (
      <p role="alert" className="error">
        {messageOf(branches.error)}
      </p>
    );
  }
  if (branches.data.length === 0) {
    return <p>Your clinic has no branches yet. An admin must add one first.</p>;
  }

  const people = clinicians.data ?? [];

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="mb-0">Today&apos;s queue</h1>
        <div className="flex flex-wrap items-end gap-3">
          {branches.data.length > 1 && (
            <div className="field">
              <label htmlFor="branch">Branch</label>
              <select
                id="branch"
                value={branchId ?? ""}
                onChange={(event) => {
                  setBranchId(event.target.value);
                  rememberBranch(event.target.value);
                }}
              >
                {branches.data.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button className="button-secondary" type="button" onClick={refresh}>
            Refresh
          </button>
        </div>
      </div>

      {form === "none" && (
        <div className="flex flex-wrap gap-3">
          <button className="button" type="button" onClick={() => setForm("walk-in")}>
            Walk-in
          </button>
          <button className="button-secondary" type="button" onClick={() => setForm("book")}>
            Book a visit
          </button>
        </div>
      )}
      {form === "walk-in" && branchId && (
        <WalkInForm
          branchId={branchId}
          clinicians={people}
          onDone={formDone}
          onCancel={() => setForm("none")}
        />
      )}
      {form === "book" && branchId && (
        <BookVisitForm
          branchId={branchId}
          clinicians={people}
          onDone={formDone}
          onCancel={() => setForm("none")}
        />
      )}

      <section aria-labelledby="queue-heading" className="card">
        <h2 id="queue-heading" className="mb-0">
          Now
        </h2>
        {queue.isPending && <p>Loading the queue...</p>}
        {queue.isError && (
          <p role="alert" className="error">
            {messageOf(queue.error)}
          </p>
        )}
        {queue.data && queue.data.length === 0 && <p>Nobody is waiting.</p>}
        {queue.data && queue.data.length > 0 && (
          <ol className="grid gap-2">
            {queue.data.map((entry) => (
              <li
                key={entry.appointment_id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2"
              >
                <span className="w-8 text-lg font-bold" aria-label="Place in line">
                  {entry.position ?? "-"}
                </span>
                <span className="font-semibold">{entry.patient_name}</span>
                <StatusBadge status={entry.status} />
                <span className="text-sm">
                  {entry.status === "in_consult"
                    ? `with ${clinicianName(people, entry.clinician_id)}`
                    : `waiting ${waitedFor(entry.checked_in_at ?? entry.scheduled_at)}`}
                  {" · "}
                  {KIND_LABELS[entry.kind] ?? entry.kind}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="day-heading" className="card">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="day-heading" className="mb-0">
            Visits on this day
          </h2>
          <div className="field">
            <label htmlFor="day">Day</label>
            <input
              id="day"
              type="date"
              value={day}
              onChange={(event) => event.target.value && setDay(event.target.value)}
            />
          </div>
        </div>
        {dayList.isPending && <p>Loading visits...</p>}
        {dayList.isError && (
          <p role="alert" className="error">
            {messageOf(dayList.error)}
          </p>
        )}
        {(change.isError || begin.isError) && (
          <p role="alert" className="error">
            {messageOf(change.error ?? begin.error)}
          </p>
        )}
        {dayList.data && dayList.data.length === 0 && <p>No visits on this day.</p>}
        {dayList.data && dayList.data.length > 0 && (
          <ul className="grid gap-2">
            {dayList.data.map((entry) => (
              <li
                key={entry.appointment_id}
                className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line pt-2"
              >
                <span className="w-14 font-mono">{formatTime(entry.starts_at)}</span>
                <span className="font-semibold">{entry.patient_name}</span>
                <StatusBadge status={entry.status} />
                <span className="text-sm">{clinicianName(people, entry.clinician_id)}</span>
                {confirming?.id === entry.appointment_id ? (
                  <span role="group" className="ml-auto flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold">
                      {confirming.button.confirm} This cannot be undone.
                    </span>
                    <button
                      type="button"
                      className="button"
                      disabled={change.isPending}
                      onClick={() => change.mutate({ entry, action: confirming.button.action })}
                    >
                      {change.isPending ? "Saving..." : "Yes"}
                    </button>
                    <button
                      type="button"
                      className="button-secondary"
                      disabled={change.isPending}
                      onClick={() => setConfirming(null)}
                    >
                      No, keep it
                    </button>
                  </span>
                ) : (
                  <span className="ml-auto flex flex-wrap gap-2">
                    {canConsult && (entry.status === "waiting" || entry.status === "in_consult") && (
                      <button
                        type="button"
                        className="button"
                        disabled={begin.isPending}
                        onClick={() => begin.mutate(entry)}
                        aria-label={`${
                          entry.status === "waiting" ? "Start visit" : "Open record"
                        }: ${entry.patient_name}`}
                      >
                        {entry.status === "waiting" ? "Start visit" : "Open record"}
                      </button>
                    )}
                    {(ACTIONS[entry.status] ?? []).map((button) => (
                      <button
                        key={button.action}
                        type="button"
                        className={button.confirm ? "button-secondary" : "button"}
                        disabled={change.isPending}
                        onClick={() =>
                          button.confirm
                            ? setConfirming({ id: entry.appointment_id, button })
                            : change.mutate({ entry, action: button.action })
                        }
                        aria-label={`${button.label}: ${entry.patient_name}`}
                      >
                        {button.label}
                      </button>
                    ))}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
