"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { addDays, daysIn } from "@/features/reports/view";
import { errorMessage } from "@/lib/api-client";
import { formatDate, formatDateTime, todayInLagos } from "@/lib/format";

import {
  CHANNEL_LABELS,
  MAX_DAYS,
  REMINDER_STATUSES,
  STATUS_LABELS,
  describeReason,
  getReminders,
  retryReminder,
  type ReminderLine,
  type ReminderStatus,
} from "./api";

const STATUS_BADGES: Record<ReminderStatus, string> = {
  pending: "bg-gray-200 text-gray-800",
  sent: "bg-accent-soft text-accent",
  failed: "bg-amber-100 text-amber-900",
  cancelled: "bg-gray-100 text-gray-700",
};

function rangeProblem(from: string, to: string): string | null {
  if (!from || !to) return "Choose both days.";
  if (from > to) return "The first day must not come after the last day.";
  if (daysIn(from, to) > MAX_DAYS) return `Choose at most ${MAX_DAYS} days.`;
  return null;
}

/*
 * The notification console (Week 11), for admins: which reminders went out, which are
 * waiting, which failed and why. A failed reminder whose visit is still booked and ahead
 * can be tried again (after the phone number is fixed, or the SMS provider is back).
 */
export function ReminderConsole() {
  const today = todayInLagos();
  const [from, setFrom] = useState(addDays(today, -6));
  const [to, setTo] = useState(today);
  const [status, setStatus] = useState<ReminderStatus | null>(null);
  const problem = rangeProblem(from, to);
  const reminders = useQuery({
    queryKey: ["reminders", from, to, status],
    queryFn: () => getReminders(from, to, status),
    enabled: problem === null,
  });
  const data = reminders.data;

  return (
    <section className="grid gap-6">
      <div>
        <p className="eyebrow">Admin</p>
        <h1 className="mb-1">Reminders</h1>
        <p className="m-0 text-sm">
          What the reminder worker did, by the day each reminder was due (Lagos time). No
          patient names or phone numbers are shown.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="field">
          <label htmlFor="reminders-from">From</label>
          <input
            id="reminders-from"
            type="date"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="reminders-to">To</label>
          <input
            id="reminders-to"
            type="date"
            value={to}
            onChange={(event) => setTo(event.target.value)}
          />
        </div>
      </div>
      {problem && (
        <p role="alert" className="error">
          {problem}
        </p>
      )}

      {data && (
        <div className="grid gap-4 sm:grid-cols-4">
          {REMINDER_STATUSES.map((value) => (
            <div key={value} className="card gap-1">
              <span className="text-sm">{STATUS_LABELS[value]}</span>
              <span className="font-display text-3xl font-bold text-ink">
                {data.counts[value] ?? 0}
              </span>
            </div>
          ))}
        </div>
      )}

      {data && Object.keys(data.failures).length > 0 && (
        <section className="card gap-2">
          <h2 className="mb-0 text-base">Why reminders did not go out</h2>
          <ul className="m-0 grid gap-1">
            {Object.entries(data.failures).map(([code, count]) => (
              <li key={code} className="flex gap-3">
                <span className="grow">{describeReason(code)}</span>
                <span className="font-mono">{count}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div role="group" aria-label="Show" className="flex flex-wrap gap-2">
        {[null, ...REMINDER_STATUSES].map((value) => (
          <button
            key={value ?? "all"}
            type="button"
            className={status === value ? "button" : "button-secondary"}
            aria-pressed={status === value}
            onClick={() => setStatus(value)}
          >
            {value ? STATUS_LABELS[value] : "All"}
          </button>
        ))}
      </div>

      <section className="card" aria-live="polite">
        {!problem && reminders.isPending && <p>Loading...</p>}
        {reminders.isError && (
          <p role="alert" className="error">
            {errorMessage(reminders.error)}
          </p>
        )}
        {data?.lines.length === 0 && <p className="m-0">No reminders in these days.</p>}
        <ul className="m-0 grid gap-3">
          {data?.lines.map((line) => <ReminderRow key={line.id} line={line} />)}
        </ul>
        {data?.more && (
          <p className="mt-3 mb-0 text-sm">
            Only the newest {data.lines.length} are listed. Choose fewer days to see the rest.
          </p>
        )}
      </section>

      {data && (
        <p className="m-0 text-sm">
          {formatDate(data.from_day)} to {formatDate(data.to_day)}.
        </p>
      )}
    </section>
  );
}

function visitText(line: ReminderLine): string {
  if (!line.visit_starts_at) return "visit not found";
  const where = line.visit_type === "teleconsult" ? "remote" : "clinic";
  return `for a ${where} visit at ${formatDateTime(line.visit_starts_at)}`;
}

function ReminderRow({ line }: { line: ReminderLine }) {
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: () => retryReminder(line.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["reminders"] }),
  });

  return (
    <li className="grid gap-1 border-t border-line pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`badge ${STATUS_BADGES[line.status]}`}>{STATUS_LABELS[line.status]}</span>
        <span>{CHANNEL_LABELS[line.channel] ?? line.channel}</span>
        <span className="text-sm">{visitText(line)}</span>
        {line.can_retry && (
          <button
            type="button"
            className="button-secondary ml-auto"
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
          >
            {retry.isPending ? "Queuing..." : "Try again"}
          </button>
        )}
      </div>
      <p className="m-0 text-sm">
        {line.sent_at
          ? `Sent ${formatDateTime(line.sent_at)}`
          : `Due ${formatDateTime(line.due_at)}`}
        {line.attempts > 0 && ` · ${line.attempts} attempt(s)`}
        {line.last_error && ` · ${describeReason(line.last_error)}`}
      </p>
      {retry.isError && (
        <p role="alert" className="error">
          {errorMessage(retry.error)}
        </p>
      )}
    </li>
  );
}
