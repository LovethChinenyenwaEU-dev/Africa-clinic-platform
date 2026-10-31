"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { METHOD_LABELS, label } from "@/features/billing/labels";
import { formatNaira } from "@/features/billing/money";
import { errorMessage } from "@/lib/api-client";
import { formatDate, todayInLagos } from "@/lib/format";

import { getDashboard } from "./api";
import type { Dashboard as DashboardData, DashboardDay } from "./schemas";
import {
  PRESETS,
  barShares,
  lastDays,
  minutes,
  percent,
  rangeProblem,
  shortDay,
  type Preset,
} from "./view";

/*
 * The clinic dashboard (Week 11, P-11), for admins: how the clinic is doing over some
 * days. Counts and sums only, never a patient's name. The backend works every number
 * out; this screen only shows them and says how each is counted.
 */
export function Dashboard() {
  const today = todayInLagos();
  const [range, setRange] = useState(lastDays(7, today));
  const [preset, setPreset] = useState<Preset | null>(7);
  const problem = rangeProblem(range.from, range.to);
  const dashboard = useQuery({
    queryKey: ["dashboard", range.from, range.to],
    queryFn: () => getDashboard(range.from, range.to),
    enabled: problem === null,
  });

  function choose(days: Preset) {
    setPreset(days);
    setRange(lastDays(days, today));
  }

  function setDay(end: "from" | "to", value: string) {
    setPreset(null);
    setRange((current) => ({ ...current, [end]: value }));
  }

  return (
    <section className="grid gap-6">
      <div>
        <p className="eyebrow">Reports</p>
        <h1 className="mb-1">Clinic dashboard</h1>
        <p className="m-0 text-sm">
          {problem
            ? "Choose the days to show."
            : `${formatDate(range.from)} to ${formatDate(range.to)}, Lagos time.`}{" "}
          Counts only: no patient is named here.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div role="group" aria-label="Show" className="flex flex-wrap gap-2">
          {PRESETS.map((days) => (
            <button
              key={days}
              type="button"
              className={preset === days ? "button" : "button-secondary"}
              aria-pressed={preset === days}
              onClick={() => choose(days)}
            >
              Last {days} days
            </button>
          ))}
        </div>
        <div className="field">
          <label htmlFor="dashboard-from">From</label>
          <input
            id="dashboard-from"
            type="date"
            max={today}
            value={range.from}
            onChange={(event) => setDay("from", event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="dashboard-to">To</label>
          <input
            id="dashboard-to"
            type="date"
            max={today}
            value={range.to}
            onChange={(event) => setDay("to", event.target.value)}
          />
        </div>
      </div>

      {problem && (
        <p role="alert" className="error">
          {problem}
        </p>
      )}
      {!problem && dashboard.isPending && <p>Loading...</p>}
      {!problem && dashboard.isError && (
        <p role="alert" className="error">
          {errorMessage(dashboard.error)}
        </p>
      )}
      {!problem && dashboard.data && <Numbers data={dashboard.data} />}
    </section>
  );
}

function Numbers({ data }: { data: DashboardData }) {
  const { visits, waits, revenue, sync, record_access: access } = data;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          title="Visits"
          value={String(visits.total)}
          note={`${visits.walk_ins} walk-in, ${visits.cancelled} cancelled`}
        />
        <Tile
          title="No-show rate"
          value={percent(visits.no_show_rate)}
          note={`${visits.no_shows} booked patient(s) never came`}
        />
        <Tile
          title="Consultations completed"
          value={percent(visits.completion_rate)}
          note={`${visits.done} of ${visits.checked_in} who checked in`}
        />
        <Tile
          title="Median wait"
          value={minutes(waits.median_minutes)}
          note={`1 in 10 waited ${minutes(waits.p90_minutes)} or more; ${waits.over_an_hour} over an hour`}
        />
      </div>

      <VisitsChart days={data.days} />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card gap-3">
          <h2 className="mb-0 text-base">Money</h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
            <Row
              term="Received"
              value={`${formatNaira(revenue.received_kobo)} (${revenue.payments})`}
            />
            <Row
              term="Given back"
              value={`${formatNaira(revenue.refunded_kobo)} (${revenue.refunds})`}
            />
            <Row term="Net" value={formatNaira(revenue.net_kobo)} strong />
            <Row
              term="Billed"
              value={`${formatNaira(revenue.billed_kobo)} (${revenue.invoices_issued} invoice(s))`}
            />
          </dl>
          {revenue.by_method.length > 0 && (
            <ul className="m-0 grid gap-1 border-t border-line pt-2 text-sm">
              {revenue.by_method.map((row) => (
                <li key={row.method} className="flex gap-3">
                  <span className="grow">
                    {label(METHOD_LABELS, row.method)} ({row.count})
                  </span>
                  <span className="font-mono">{formatNaira(row.amount_kobo)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card gap-3">
          <h2 className="mb-0 text-base">Sync and sending</h2>
          <ul className="m-0 grid gap-2">
            <SyncCheck count={sync.late_entries} text="offline entries arrived after sign-off" />
            <SyncCheck
              count={sync.open_conflicts}
              text="record versions waiting for a clinician to choose (now)"
            />
            <SyncCheck count={sync.registrations_to_review} text="offline registrations to review (now)" />
            <SyncCheck count={sync.reminders_failed} text="reminders that could not be sent" />
            <SyncCheck count={sync.online_payments_failed} text="online payments that failed" />
          </ul>
          <p className="m-0 text-sm">{sync.reminders_sent} reminder(s) sent.</p>
        </section>
      </div>

      <section className="card gap-3">
        <h2 className="mb-0 text-base">Who opened patient records</h2>
        <p className="m-0 text-sm">
          {access.events} audit line(s) about {access.patients} patient(s), written by staff.
          The full detail is in the audit log.
        </p>
        {access.by_staff.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="py-1 font-semibold">Staff member</th>
                <th className="py-1 text-right font-semibold">Lines</th>
                <th className="py-1 text-right font-semibold">Patients</th>
              </tr>
            </thead>
            <tbody>
              {access.by_staff.map((row) => (
                <tr key={row.staff_id} className="border-t border-line">
                  <td className="py-1">{row.name}</td>
                  <td className="py-1 text-right font-mono">{row.events}</td>
                  <td className="py-1 text-right font-mono">{row.patients}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <details className="card text-sm">
        <summary className="cursor-pointer font-semibold">How these are counted</summary>
        <ul className="mt-2 grid gap-1">
          <li>Visits are the ones whose start time falls in these days.</li>
          <li>
            No-show rate: of the booked patients who were due, how many never came. Walk-ins
            cannot be no-shows.
          </li>
          <li>Completed: of the patients who checked in, how many finished their consultation.</li>
          <li>Wait: from check-in to the start of the consultation.</li>
          <li>Money: payments received, refunds approved and invoices issued in these days.</li>
          <li>Items marked "now" are what is waiting today, whatever days are chosen.</li>
        </ul>
      </details>
    </>
  );
}

function Tile({ title, value, note }: { title: string; value: string; note: string }) {
  return (
    <div className="card gap-1">
      <span className="text-sm">{title}</span>
      <span className="font-display text-3xl font-bold text-ink">{value}</span>
      <span className="text-sm">{note}</span>
    </div>
  );
}

function Row({ term, value, strong = false }: { term: string; value: string; strong?: boolean }) {
  return (
    <>
      <dt className={strong ? "font-semibold" : ""}>{term}</dt>
      <dd className={`m-0 text-right font-mono ${strong ? "font-bold" : ""}`}>{value}</dd>
    </>
  );
}

// A problem shows an icon and words, never colour alone.
function SyncCheck({ count, text }: { count: number; text: string }) {
  const Icon = count ? TriangleAlert : CircleCheck;
  return (
    <li className="flex items-start gap-2">
      <Icon
        aria-hidden
        className={`mt-0.5 size-4 shrink-0 ${count ? "text-amber-700" : "text-teal"}`}
      />
      <span>
        <strong className="font-mono">{count}</strong> {text}
      </span>
    </li>
  );
}

function dayText(day: DashboardDay): string {
  return (
    `${formatDate(day.day)}: ${day.visits} visit(s), ${day.done} completed, ` +
    `${day.no_shows} no-show(s), median wait ${minutes(day.median_wait_minutes)}, ` +
    `${formatNaira(day.received_kobo)} received`
  );
}

/*
 * Visits per day: one series, so no legend; the title names it. Hover or focus a day
 * for its numbers; the same numbers are in the table underneath.
 */
function VisitsChart({ days }: { days: DashboardDay[] }) {
  const [active, setActive] = useState<number | null>(null);
  const shares = barShares(days);
  const most = Math.max(0, ...days.map((day) => day.visits));
  const labelEvery = days.length <= 14 ? 1 : Math.ceil(days.length / 7);
  const shown = active === null ? null : days[active];

  return (
    <section className="card gap-3">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h2 className="mb-0 text-base">Visits per day</h2>
        <span className="text-sm">busiest day: {most}</span>
      </div>
      <p className="m-0 min-h-5 text-sm" aria-live="polite">
        {shown ? dayText(shown) : "Point at a day, or move to it with Tab, to see its numbers."}
      </p>
      <div
        role="group"
        aria-label="Visits per day"
        className="flex h-40 items-end gap-[2px] border-b border-line"
        onMouseLeave={() => setActive(null)}
      >
        {days.map((day, index) => (
          <div
            key={day.day}
            tabIndex={0}
            aria-label={dayText(day)}
            className="group flex h-full min-w-0 flex-1 cursor-default items-end outline-none"
            onMouseEnter={() => setActive(index)}
            onFocus={() => setActive(index)}
            onBlur={() => setActive(null)}
          >
            <div
              className={`w-full rounded-t-[4px] ${
                active === index ? "bg-teal" : "bg-accent"
              } group-focus-visible:ring-2 group-focus-visible:ring-teal`}
              style={{ height: day.visits ? `${Math.max(shares[index] * 100, 2)}%` : "0" }}
            />
          </div>
        ))}
      </div>
      <div className="flex gap-[2px] text-xs" aria-hidden>
        {days.map((day, index) => (
          <span key={day.day} className="min-w-0 flex-1 truncate text-center">
            {index % labelEvery === 0 ? shortDay(day.day) : ""}
          </span>
        ))}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer">Show as a table</summary>
        <table className="mt-2 w-full">
          <thead>
            <tr className="text-left">
              <th className="py-1 font-semibold">Day</th>
              <th className="py-1 text-right font-semibold">Visits</th>
              <th className="py-1 text-right font-semibold">Completed</th>
              <th className="py-1 text-right font-semibold">No-shows</th>
              <th className="py-1 text-right font-semibold">Median wait</th>
              <th className="py-1 text-right font-semibold">Received</th>
            </tr>
          </thead>
          <tbody>
            {days.map((day) => (
              <tr key={day.day} className="border-t border-line">
                <td className="py-1">{formatDate(day.day)}</td>
                <td className="py-1 text-right font-mono">{day.visits}</td>
                <td className="py-1 text-right font-mono">{day.done}</td>
                <td className="py-1 text-right font-mono">{day.no_shows}</td>
                <td className="py-1 text-right font-mono">{minutes(day.median_wait_minutes)}</td>
                <td className="py-1 text-right font-mono">{formatNaira(day.received_kobo)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
