"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import { getConsentHistory, getCurrentWording, recordConsent, withdrawConsent } from "./api";
import { GRANTED_BY_LABELS, PURPOSE_LABELS } from "./labels";
import { GRANTED_BY, PURPOSES, type GrantedBy, type Purpose } from "./schemas";
import { currentConsent, type ConsentState } from "./status";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : API_MESSAGES.unavailable;
}

const historyKey = (patientId: string) => ["consent", patientId];

export function ConsentPanel({ patientId }: { patientId: string }) {
  const history = useQuery({
    queryKey: historyKey(patientId),
    queryFn: () => getConsentHistory(patientId),
  });
  const states = history.data ? currentConsent(history.data) : null;

  return (
    <section aria-labelledby="consent-heading" className="card">
      <h2 id="consent-heading" className="mb-0">
        Consent
      </h2>
      {history.isPending && <p>Loading consent...</p>}
      {history.isError && (
        <p role="alert" className="error">
          {messageOf(history.error)}
        </p>
      )}
      {states && (
        <ul className="grid gap-3">
          {PURPOSES.map((purpose) => (
            <ConsentRow
              key={purpose}
              patientId={patientId}
              purpose={purpose}
              current={states[purpose]}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function StatusLine({ current }: { current: ConsentState }) {
  if (current.state === "agreed") {
    const by = GRANTED_BY_LABELS[current.consent.granted_by as GrantedBy] ?? "someone";
    return (
      <p className="text-sm">
        <span className="badge bg-green-100 text-green-900">Agreed</span>{" "}
        {formatDateTime(current.consent.granted_at)} by {by} (wording version{" "}
        {current.consent.wording_version})
      </p>
    );
  }
  if (current.state === "withdrawn") {
    return (
      <p className="text-sm">
        <span className="badge bg-red-100 text-red-900">Withdrawn</span>{" "}
        {formatDateTime(current.consent.revoked_at ?? current.consent.granted_at)}
      </p>
    );
  }
  return (
    <p className="text-sm">
      <span className="badge bg-gray-200 text-gray-800">Not recorded</span>
    </p>
  );
}

function ConsentRow({
  patientId,
  purpose,
  current,
}: {
  patientId: string;
  purpose: Purpose;
  current: ConsentState;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"idle" | "recording" | "withdrawing">("idle");
  const [grantedBy, setGrantedBy] = useState<GrantedBy>("patient");

  // The wording is only fetched when someone is about to record an agreement.
  const wording = useQuery({
    queryKey: ["consent-wording", purpose],
    queryFn: () => getCurrentWording(purpose),
    enabled: mode === "recording",
  });

  const done = () => {
    setMode("idle");
    void queryClient.invalidateQueries({ queryKey: historyKey(patientId) });
  };
  const record = useMutation({
    mutationFn: () => recordConsent(patientId, purpose, grantedBy),
    onSuccess: done,
  });
  const withdraw = useMutation({
    mutationFn: () => withdrawConsent(patientId, purpose),
    onSuccess: done,
  });

  const busy = record.isPending || withdraw.isPending;
  const failure = record.error ?? withdraw.error;
  const headingId = `consent-${purpose}`;

  function cancel() {
    setMode("idle");
    record.reset();
    withdraw.reset();
  }

  return (
    <li aria-labelledby={headingId} className="grid gap-2 border-t border-line pt-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p id={headingId} className="font-semibold">
            {PURPOSE_LABELS[purpose]}
          </p>
          <StatusLine current={current} />
        </div>
        {mode === "idle" &&
          (current.state === "agreed" ? (
            <button className="button-secondary" type="button" onClick={() => setMode("withdrawing")}>
              Withdraw
            </button>
          ) : (
            <button className="button-secondary" type="button" onClick={() => setMode("recording")}>
              Record agreement
            </button>
          ))}
      </div>

      {mode === "recording" && (
        <div className="grid gap-3 rounded-md bg-canvas p-3">
          {wording.isPending && <p>Loading the wording...</p>}
          {wording.isError && (
            <p role="alert" className="error">
              {messageOf(wording.error)}
            </p>
          )}
          {wording.data === null && (
            <p className="notice">
              Your clinic has not published wording for this yet. An admin must add it before an
              agreement can be recorded.
            </p>
          )}
          {wording.data && (
            <>
              <p className="text-sm font-semibold">
                Read this to the patient (wording version {wording.data.version}):
              </p>
              <blockquote className="whitespace-pre-wrap border-l-4 border-accent bg-white p-3">
                {wording.data.body}
              </blockquote>
              <fieldset className="grid gap-1" disabled={busy}>
                <legend className="font-semibold">Who agreed?</legend>
                {GRANTED_BY.map((option) => (
                  <label key={option} className="flex items-center gap-2 font-normal">
                    <input
                      type="radio"
                      name={`granted-by-${purpose}`}
                      value={option}
                      checked={grantedBy === option}
                      onChange={() => setGrantedBy(option)}
                    />
                    {option === "patient" ? "The patient" : "A caregiver, on their behalf"}
                  </label>
                ))}
              </fieldset>
            </>
          )}
          <div className="flex flex-wrap gap-3">
            {wording.data && (
              <button
                className="button"
                type="button"
                onClick={() => record.mutate()}
                disabled={busy}
              >
                {record.isPending ? "Saving..." : "They agreed: save"}
              </button>
            )}
            <button className="button-secondary" type="button" onClick={cancel} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {mode === "withdrawing" && (
        <div className="notice grid gap-3">
          <p>
            Withdraw agreement to {PURPOSE_LABELS[purpose].toLowerCase()}? The record is kept and
            marked as withdrawn.
          </p>
          <div className="flex flex-wrap gap-3">
            <button className="button" type="button" onClick={() => withdraw.mutate()} disabled={busy}>
              {withdraw.isPending ? "Withdrawing..." : "Yes, withdraw"}
            </button>
            <button className="button-secondary" type="button" onClick={cancel} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {failure && (
        <p role="alert" className="error">
          {messageOf(failure)}
        </p>
      )}
    </li>
  );
}
