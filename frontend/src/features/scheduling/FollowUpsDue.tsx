"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";
import { formatDate, todayInLagos } from "@/lib/format";

import { cancelFollowUp, getFollowUpsDue, markFollowUpBooked } from "./api";
import { VISIT_TYPE_LABELS } from "./labels";

const DAYS_AHEAD = 14;

/** The Lagos day `days` after today, "2026-11-16". */
export function lagosDayPlus(days: number, today: string = todayInLagos()): string {
  const [year, month, day] = today.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

/*
 * Follow-ups clinicians asked for, due in the next two weeks or overdue (FR-C5).
 * Front desk books the visit with "Book a visit", then marks the follow-up booked.
 * Names, dates and the kind of visit only: the clinical instructions stay in the record.
 */
export function FollowUpsDue({ canBook }: { canBook: boolean }) {
  const queryClient = useQueryClient();
  const until = lagosDayPlus(DAYS_AHEAD);
  const key = ["follow-ups-due", until];
  const due = useQuery({ queryKey: key, queryFn: () => getFollowUpsDue(until) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["follow-ups-due"] });
  const booked = useMutation({ mutationFn: markFollowUpBooked, onSuccess: refresh });
  const cancel = useMutation({ mutationFn: cancelFollowUp, onSuccess: refresh });
  const today = todayInLagos();

  if (due.data?.length === 0) return null;

  return (
    <section aria-labelledby="follow-ups-heading" className="card">
      <h2 id="follow-ups-heading" className="mb-0">
        Follow-ups due
      </h2>
      {due.isError && <p className="error">{errorMessage(due.error)}</p>}
      <ul className="grid gap-2">
        {due.data?.map((row) => (
          <li
            key={row.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2"
          >
            <Link href={`/patients/${row.patient_id}`} className="font-semibold text-accent underline">
              {row.patient_name}
            </Link>
            <span className={row.due_date < today ? "font-semibold text-red-900" : ""}>
              {row.due_date < today ? "Overdue since" : "By"} {formatDate(row.due_date)}
            </span>
            <span className="text-sm">{VISIT_TYPE_LABELS[row.visit_type] ?? row.visit_type}</span>
            {canBook && (
              <span className="ml-auto flex flex-wrap gap-2">
                <button
                  type="button"
                  className="button-secondary"
                  disabled={booked.isPending}
                  onClick={() => booked.mutate(row.id)}
                >
                  Mark booked
                </button>
                <ConfirmAction
                  label="Not needed"
                  question="Cancel this follow-up?"
                  pending={cancel.isPending}
                  onConfirm={() => cancel.mutate(row.id)}
                />
              </span>
            )}
          </li>
        ))}
      </ul>
      {(booked.isError || cancel.isError) && (
        <p role="alert" className="error">
          {errorMessage(booked.error ?? cancel.error)}
        </p>
      )}
    </section>
  );
}
