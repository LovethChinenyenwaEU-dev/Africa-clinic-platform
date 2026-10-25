"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "@/lib/api-client";
import { formatDate, todayInLagos } from "@/lib/format";

import { exportTakings, getTakings } from "./api";
import { downloadText } from "./download";
import { FLAG_TITLES, METHOD_LABELS, label } from "./labels";
import { formatNaira } from "./money";
import type { MethodTotal, Takings } from "./schemas";

/*
 * One Lagos day's money: what came in by method and person, what went back, and the
 * net per method (net cash is what should be in the drawer). Then the things to look at.
 */
export function TakingsView() {
  const [day, setDay] = useState(todayInLagos());
  const takings = useQuery({ queryKey: ["takings", day], queryFn: () => getTakings(day) });
  const download = useMutation({
    mutationFn: () => exportTakings(day),
    onSuccess: (file) => downloadText(file.filename, file.csv),
  });

  return (
    <section className="grid gap-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="grow">
          <h1 className="mb-1">Daily takings</h1>
          <p className="m-0 text-sm">{formatDate(day)}, Lagos time, midnight to midnight.</p>
        </div>
        <div className="field">
          <label htmlFor="takings-day">Day</label>
          <input
            id="takings-day"
            type="date"
            max={todayInLagos()}
            value={day}
            onChange={(event) => event.target.value && setDay(event.target.value)}
          />
        </div>
        <button
          type="button"
          className="button-secondary"
          disabled={download.isPending}
          onClick={() => download.mutate()}
        >
          Download CSV
        </button>
      </div>
      {download.isError && (
        <p role="alert" className="error">
          {errorMessage(download.error)}
        </p>
      )}
      {takings.isPending && <p>Loading...</p>}
      {takings.isError && (
        <p role="alert" className="error">
          {errorMessage(takings.error)}
        </p>
      )}
      {takings.data && <Day takings={takings.data} />}
    </section>
  );
}

function Day({ takings }: { takings: Takings }) {
  const cash = takings.net_by_method.find((row) => row.method === "cash");

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-4">
        <Figure title="Money in" kobo={takings.total_in_kobo} />
        <Figure title="Given back" kobo={takings.total_out_kobo} />
        <Figure title="Net" kobo={takings.net_kobo} />
        <Figure title="Cash in the drawer" kobo={cash?.amount_kobo ?? 0} strong />
      </div>
      <p className="m-0 text-sm">
        {takings.invoices_issued} invoice(s) issued, for {formatNaira(takings.billed_kobo)}.
      </p>

      <Flags takings={takings} />

      <div className="grid gap-6 md:grid-cols-3">
        <ByMethod title="In" rows={takings.money_in} />
        <ByMethod title="Given back" rows={takings.money_out} />
        <ByMethod title="Net" rows={takings.net_by_method} />
      </div>

      <section aria-labelledby="by-staff-heading" className="card">
        <h2 id="by-staff-heading" className="mb-0">
          Taken by
        </h2>
        {takings.by_staff.length === 0 && <p>No payments this day.</p>}
        <ul className="grid gap-1">
          {takings.by_staff.map((row) => (
            <li key={row.staff_id} className="flex gap-3 border-t border-line pt-1">
              <span className="grow">{row.name}</span>
              <span className="text-sm">{row.payments} payment(s)</span>
              <span className="font-mono">{formatNaira(row.taken_kobo)}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function Figure({ title, kobo, strong = false }: { title: string; kobo: number; strong?: boolean }) {
  return (
    <div className="card gap-1">
      <span className="text-sm">{title}</span>
      <span className={`font-mono ${strong ? "text-2xl font-bold text-accent" : "text-xl"}`}>
        {formatNaira(kobo)}
      </span>
    </div>
  );
}

function ByMethod({ title, rows }: { title: string; rows: MethodTotal[] }) {
  return (
    <section className="card gap-2">
      <h2 className="mb-0 text-base">{title}</h2>
      {rows.length === 0 && <p className="m-0 text-sm">Nothing.</p>}
      <ul className="grid gap-1">
        {rows.map((row) => (
          <li key={row.method} className="flex gap-3">
            <span className="grow">
              {label(METHOD_LABELS, row.method)} <span className="text-sm">({row.count})</span>
            </span>
            <span className="font-mono">{formatNaira(row.amount_kobo)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Flags({ takings }: { takings: Takings }) {
  if (takings.flags.length === 0) {
    return <p className="m-0 text-sm">Nothing unusual to look at.</p>;
  }
  return (
    <section aria-labelledby="flags-heading" className="notice grid gap-2">
      <h2 id="flags-heading" className="mb-0">
        To look at ({takings.flags.length})
      </h2>
      <ul className="grid gap-2">
        {takings.flags.map((flag, index) => (
          <li key={`${flag.kind}-${index}`}>
            <span className="font-semibold">{label(FLAG_TITLES, flag.kind)}</span>
            {flag.invoice_number && <span className="font-mono"> · {flag.invoice_number}</span>}
            <br />
            <span className="text-sm">{flag.message}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
