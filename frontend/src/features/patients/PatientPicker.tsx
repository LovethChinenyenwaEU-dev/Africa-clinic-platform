"use client";

import { useMutation } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";

import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { ageFrom, formatDate } from "@/lib/format";

import { MIN_SEARCH_LENGTH, searchPatients } from "./api";
import type { Patient } from "./schemas";

/**
 * Find and choose one patient inside another form (walk-in, booking).
 * Searching only happens on the button: every search is written in the diary.
 */
export function PatientPicker({
  chosen,
  onChoose,
}: {
  chosen: Patient | null;
  onChoose: (patient: Patient | null) => void;
}) {
  const inputId = useId();
  const [text, setText] = useState("");
  const [tooShort, setTooShort] = useState(false);
  const search = useMutation({ mutationFn: searchPatients });

  if (chosen) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-white p-3">
        <span>
          <span className="font-semibold">{chosen.full_name}</span>
          <span className="text-sm">
            {" "}
            · born {formatDate(chosen.date_of_birth)} ({ageFrom(chosen.date_of_birth)})
          </span>
        </span>
        <button className="button-secondary ml-auto" type="button" onClick={() => onChoose(null)}>
          Change patient
        </button>
      </div>
    );
  }

  function find(event?: FormEvent) {
    event?.preventDefault();
    const trimmed = text.trim();
    setTooShort(trimmed.length < MIN_SEARCH_LENGTH);
    if (trimmed.length >= MIN_SEARCH_LENGTH) search.mutate(trimmed);
  }

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="field min-w-56 flex-1">
          <label htmlFor={inputId}>Patient name or phone</label>
          <input
            id={inputId}
            type="search"
            autoComplete="off"
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") find(event); // never submit the outer form by accident
            }}
            aria-invalid={tooShort}
          />
        </div>
        <button className="button-secondary" type="button" onClick={() => find()}>
          {search.isPending ? "Searching..." : "Find"}
        </button>
      </div>
      {tooShort && <p className="error">Type at least {MIN_SEARCH_LENGTH} characters.</p>}
      {search.isError && (
        <p role="alert" className="error">
          {search.error instanceof ApiError ? search.error.message : API_MESSAGES.unavailable}
        </p>
      )}
      {search.data && search.data.length === 0 && (
        <p className="text-sm">No patients found. Register them on the Patients screen first.</p>
      )}
      {search.data && search.data.length > 0 && (
        <ul className="grid gap-1" aria-label="Matching patients">
          {search.data.map((patient) => (
            <li key={patient.id}>
              <button
                type="button"
                onClick={() => onChoose(patient)}
                className="w-full rounded-md border border-line bg-white p-2 text-left hover:border-accent"
              >
                <span className="font-semibold">{patient.full_name}</span>
                <span className="text-sm">
                  {" "}
                  · born {formatDate(patient.date_of_birth)}
                  {patient.phone && ` · ${patient.phone}`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
