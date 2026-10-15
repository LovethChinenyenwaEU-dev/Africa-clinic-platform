"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ROLE_LABELS } from "@/features/identity/roles";
import type { Role } from "@/features/identity/schemas";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import {
  MAX_EVENTS,
  NO_FILTERS,
  auditQuery,
  getAuditEvents,
  getStaff,
  type AuditFilters,
} from "./api";
import { SYSTEM_ACTOR_ID, describeAction, isRead } from "./labels";

const short = (id: string) => id.slice(0, 8);

export function AuditLog() {
  const [draft, setDraft] = useState<AuditFilters>(NO_FILTERS);
  // The query actually sent. Nothing is read until Show is pressed: each read is logged.
  const [query, setQuery] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [onlyLooks, setOnlyLooks] = useState(false);

  const staff = useQuery({ queryKey: ["staff"], queryFn: getStaff });
  const events = useQuery({
    queryKey: ["audit", query],
    queryFn: () => getAuditEvents(query ?? ""),
    enabled: query !== null,
  });

  function show(filters: AuditFilters) {
    const result = auditQuery(filters);
    if ("problem" in result) {
      setProblem(result.problem);
      return;
    }
    setProblem(null);
    if (result.query === query) {
      void events.refetch(); // same filters again: read again on purpose
    } else {
      setQuery(result.query);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    show(draft);
  }

  function whoIs(actorId: string): string {
    if (actorId === SYSTEM_ACTOR_ID) return "The system";
    const person = staff.data?.find((member) => member.id === actorId);
    if (!person) return `Unknown staff (${short(actorId)})`;
    const role = ROLE_LABELS[person.role as Role] ?? person.role;
    return `${person.full_name} (${role})${person.is_active ? "" : ", switched off"}`;
  }

  function filterToPatient(patientId: string) {
    const next = { ...draft, patientId };
    setDraft(next);
    show(next);
  }

  const shown = (events.data ?? []).filter((event) => !onlyLooks || isRead(event.action));

  return (
    <section className="grid gap-6">
      <div>
        <h1 className="mb-1">Audit log</h1>
        <p className="text-sm">
          Who did what, and when. Patients appear by ID only: admins do not see patient
          details. Reading this log is itself recorded.
        </p>
      </div>

      <form className="card grid gap-3 sm:grid-cols-2" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="audit-staff">Staff member</label>
          <select
            id="audit-staff"
            value={draft.staffId}
            onChange={(event) => setDraft({ ...draft, staffId: event.target.value })}
          >
            <option value="">Everyone</option>
            {staff.data?.map((member) => (
              <option key={member.id} value={member.id}>
                {whoIs(member.id)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="audit-patient">Patient ID (optional)</label>
          <input
            id="audit-patient"
            autoComplete="off"
            placeholder="ask staff for the patient's ID"
            value={draft.patientId}
            onChange={(event) => setDraft({ ...draft, patientId: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="audit-from">From (Lagos day)</label>
          <input
            id="audit-from"
            type="date"
            value={draft.fromDay}
            onChange={(event) => setDraft({ ...draft, fromDay: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="audit-to">To (Lagos day, included)</label>
          <input
            id="audit-to"
            type="date"
            value={draft.toDay}
            onChange={(event) => setDraft({ ...draft, toDay: event.target.value })}
          />
        </div>
        {problem && <p className="error sm:col-span-2">{problem}</p>}
        <div className="flex flex-wrap gap-3 sm:col-span-2">
          <button className="button" type="submit" disabled={events.isFetching}>
            {events.isFetching ? "Loading..." : "Show"}
          </button>
          <button
            className="button-secondary"
            type="button"
            onClick={() => {
              setDraft(NO_FILTERS);
              setProblem(null);
            }}
          >
            Clear filters
          </button>
        </div>
      </form>

      {events.isError && (
        <p role="alert" className="error">
          {errorMessage(events.error)}
        </p>
      )}

      {events.data && (
        <section aria-labelledby="audit-results" className="card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="audit-results" className="mb-0">
              {events.data.length === MAX_EVENTS
                ? `Latest ${MAX_EVENTS} lines (narrow the filters to see older ones)`
                : `${events.data.length} lines`}
            </h2>
            <label className="flex items-center gap-2 text-sm font-normal">
              <input
                type="checkbox"
                checked={onlyLooks}
                onChange={(event) => setOnlyLooks(event.target.checked)}
              />
              Only show who looked (views and searches)
            </label>
          </div>
          {shown.length === 0 ? (
            <p>No lines match.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line">
                    <th className="py-2 pr-3">When</th>
                    <th className="py-2 pr-3">Who</th>
                    <th className="py-2 pr-3">What</th>
                    <th className="py-2 pr-3">Patient</th>
                    <th className="py-2">Record</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((event) => (
                    <tr key={event.id} className="border-b border-line align-top">
                      <td className="py-2 pr-3 whitespace-nowrap">
                        {formatDateTime(event.occurred_at)}
                      </td>
                      <td className="py-2 pr-3">{whoIs(event.actor_id)}</td>
                      <td className="py-2 pr-3">
                        {describeAction(event.action)}
                        {isRead(event.action) && (
                          <span className="badge ml-2 bg-amber-100 text-amber-900">Look</span>
                        )}
                      </td>
                      <td className="py-2 pr-3 font-mono">
                        {event.patient_id ? (
                          <button
                            type="button"
                            className="text-accent underline"
                            title={event.patient_id}
                            onClick={() => filterToPatient(event.patient_id ?? "")}
                            aria-label={`Show only patient ${event.patient_id}`}
                          >
                            {short(event.patient_id)}
                          </button>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="py-2 font-mono" title={event.entity_id ?? undefined}>
                        {event.entity_id ? short(event.entity_id) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </section>
  );
}
