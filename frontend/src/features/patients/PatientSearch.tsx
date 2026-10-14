"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { ageFrom, formatDate } from "@/lib/format";

import { MIN_SEARCH_LENGTH, searchPatients } from "./api";
import { SEX_LABELS } from "./labels";

// The backend returns at most this many, so a full page means "narrow your search".
const MAX_RESULTS = 25;

export function PatientSearch({ canRegister }: { canRegister: boolean }) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState<string | null>(null);
  const [tooShort, setTooShort] = useState(false);

  // Only searches when the person presses Search: every search is written in the diary.
  const results = useQuery({
    queryKey: ["patients", "search", query],
    queryFn: () => searchPatients(query ?? ""),
    enabled: query !== null,
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed.length < MIN_SEARCH_LENGTH) {
      setTooShort(true);
      return;
    }
    setTooShort(false);
    if (trimmed === query) {
      void results.refetch(); // the same words again: search again on purpose
    } else {
      setQuery(trimmed);
    }
  }

  return (
    <section className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="mb-0">Patients</h1>
        {canRegister && (
          <Link href="/patients/new" className="button">
            Register a patient
          </Link>
        )}
      </div>

      <form role="search" onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="field min-w-64 flex-1">
          <label htmlFor="patient-search">Name or phone number</label>
          <input
            id="patient-search"
            type="search"
            autoComplete="off"
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-invalid={tooShort}
            aria-describedby={tooShort ? "patient-search-error" : undefined}
          />
        </div>
        <button className="button" type="submit" disabled={results.isFetching}>
          {results.isFetching ? "Searching..." : "Search"}
        </button>
        {tooShort && (
          <p id="patient-search-error" className="error w-full">
            Type at least {MIN_SEARCH_LENGTH} characters.
          </p>
        )}
      </form>

      {results.isError && (
        <p role="alert" className="error">
          {results.error instanceof ApiError ? results.error.message : API_MESSAGES.unavailable}
        </p>
      )}

      {results.data && (
        <div aria-live="polite" className="grid gap-3">
          {results.data.length === 0 ? (
            <p>
              No patients found. Check the spelling, or try their phone number.
              {canRegister && (
                <>
                  {" "}
                  <Link href="/patients/new" className="text-accent underline">
                    Register a new patient
                  </Link>
                </>
              )}
            </p>
          ) : (
            <>
              <p className="text-sm">
                {results.data.length === MAX_RESULTS
                  ? `Showing the first ${MAX_RESULTS}. Add more of the name to narrow it down.`
                  : `${results.data.length} found.`}
              </p>
              <ul className="grid gap-2">
                {results.data.map((patient) => (
                  <li key={patient.id}>
                    <Link
                      href={`/patients/${patient.id}`}
                      className="block rounded-lg border border-line bg-white p-3 hover:border-accent"
                    >
                      <span className="block font-semibold text-accent">{patient.full_name}</span>
                      <span className="block text-sm">
                        Born {formatDate(patient.date_of_birth)} ({ageFrom(patient.date_of_birth)})
                        {" · "}
                        {SEX_LABELS[patient.sex] ?? patient.sex}
                        {patient.phone && ` · ${patient.phone}`}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
