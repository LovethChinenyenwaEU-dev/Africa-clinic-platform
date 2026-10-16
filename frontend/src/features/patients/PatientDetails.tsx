"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { ConsentPanel } from "@/features/consent/ConsentPanel";
import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { ageFrom, formatDate } from "@/lib/format";

import { getPatient } from "./api";
import { SEX_LABELS } from "./labels";

export function PatientDetails({
  patientId,
  canManageConsent,
}: {
  patientId: string;
  canManageConsent: boolean;
}) {
  // Opening the page is one "patient.view" line in the diary.
  const patient = useQuery({
    queryKey: ["patient", patientId],
    queryFn: () => getPatient(patientId),
  });

  if (patient.isPending) {
    return <p>Loading patient...</p>;
  }

  if (patient.isError) {
    const notFound = patient.error instanceof ApiError && patient.error.kind === "not_found";
    return (
      <section className="grid gap-3">
        <h1 className="mb-0">{notFound ? "Patient not found" : "Could not load the patient"}</h1>
        <p role="alert">
          {notFound
            ? "This patient does not exist in your clinic."
            : patient.error instanceof ApiError
              ? patient.error.message
              : API_MESSAGES.unavailable}
        </p>
        <Link href="/patients" className="text-accent underline">
          Back to patients
        </Link>
      </section>
    );
  }

  const person = patient.data;
  return (
    <div className="grid gap-6">
      <p>
        <Link href="/patients" className="text-accent underline">
          ← Patients
        </Link>
      </p>

      <section className="card">
        <h1 className="mb-0">{person.full_name}</h1>
        {person.review_status === "needs_review" && (
          <p className="notice">
            Registered offline, and may already be registered.{" "}
            <Link href="/patients/review" className="text-accent underline">
              Review it
            </Link>{" "}
            before relying on this record.
          </p>
        )}
        {person.review_status === "duplicate" && person.duplicate_of_id && (
          <p className="notice">
            Checked: this patient was already registered. Use{" "}
            <Link href={`/patients/${person.duplicate_of_id}`} className="text-accent underline">
              the original record
            </Link>
            . This one is kept, with what was recorded on it.
          </p>
        )}
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[max-content_1fr]">
          <dt className="font-semibold">Date of birth</dt>
          <dd>
            {formatDate(person.date_of_birth)} ({ageFrom(person.date_of_birth)})
          </dd>
          <dt className="font-semibold">Sex</dt>
          <dd>{SEX_LABELS[person.sex] ?? person.sex}</dd>
          <dt className="font-semibold">Phone</dt>
          <dd>{person.phone ?? "None recorded"}</dd>
        </dl>
      </section>

      {canManageConsent && <ConsentPanel patientId={person.id} />}
    </div>
  );
}
