"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { getPatient } from "@/features/patients/api";
import { SEX_LABELS } from "@/features/patients/labels";
import { getClinicians } from "@/features/scheduling/api";
import { errorMessage } from "@/lib/api-client";
import { ageFrom, formatDate, formatDateTime } from "@/lib/format";

import { getAllergies, getPrescriptions, getProblems, getReferral } from "./api";
import { SEVERITY_LABELS, URGENCY_LABELS } from "./labels";
import { describePrescription } from "./prescribing";

/*
 * A referral letter to print or save as PDF (the browser's print does both). It
 * carries what the receiving clinician needs and nothing more: who the patient is,
 * why they are referred, their allergies, current medicines and known problems.
 */
export function ReferralLetter({ referralId }: { referralId: string }) {
  const referral = useQuery({
    queryKey: ["referral", referralId],
    queryFn: () => getReferral(referralId),
  });
  const patientId = referral.data?.patient_id;
  const encounterId = referral.data?.encounter_id;
  const ready = Boolean(patientId && encounterId);
  const patient = useQuery({
    queryKey: ["patient", patientId],
    queryFn: () => getPatient(patientId ?? ""),
    enabled: ready,
  });
  const allergies = useQuery({
    queryKey: ["allergies", patientId],
    queryFn: () => getAllergies(patientId ?? ""),
    enabled: ready,
  });
  const problems = useQuery({
    queryKey: ["problems", patientId],
    queryFn: () => getProblems(patientId ?? ""),
    enabled: ready,
  });
  const medicines = useQuery({
    queryKey: ["prescriptions", encounterId, false],
    queryFn: () => getPrescriptions(encounterId ?? ""),
    enabled: ready,
  });
  const clinicians = useQuery({ queryKey: ["clinicians"], queryFn: getClinicians });

  if (referral.isPending) return <p>Loading the referral...</p>;
  if (referral.isError) {
    return (
      <p role="alert" className="error">
        {errorMessage(referral.error)}
      </p>
    );
  }

  const letter = referral.data;
  const writer = clinicians.data?.find((person) => person.id === letter.recorded_by_id);
  const activeAllergies = (allergies.data ?? []).filter(
    (row) => row.version_status === "current" && row.clinical_status === "active",
  );
  const activeProblems = (problems.data ?? []).filter(
    (row) => row.version_status === "current" && row.clinical_status === "active",
  );
  const activeMedicines = (medicines.data ?? []).filter(
    (row) => row.version_status === "current" && row.clinical_status === "active",
  );

  return (
    <article className="grid max-w-3xl gap-5">
      <p className="flex flex-wrap gap-3 print:hidden">
        <Link href={`/encounters/${letter.encounter_id}`} className="text-accent underline">
          ← Back to the encounter
        </Link>
        <button className="button" type="button" onClick={() => window.print()}>
          Print or save as PDF
        </button>
      </p>
      {letter.status === "cancelled" && (
        <p role="alert" className="notice">
          This referral was cancelled. Do not send it.
        </p>
      )}

      <header className="grid gap-1">
        <h1 className="mb-0">Referral letter</h1>
        <p>Date: {formatDateTime(letter.written_at)}</p>
        <p>
          To: <span className="font-semibold">{letter.to_name}</span>
          {letter.specialty ? `, ${letter.specialty}` : ""}
        </p>
        <p>
          Urgency: <span className="font-semibold">{URGENCY_LABELS[letter.urgency]}</span>
        </p>
      </header>

      <section className="grid gap-1">
        <h2 className="mb-0 text-lg">Patient</h2>
        {patient.data ? (
          <p>
            {patient.data.full_name}, born {formatDate(patient.data.date_of_birth)} (
            {ageFrom(patient.data.date_of_birth)}),{" "}
            {SEX_LABELS[patient.data.sex] ?? patient.data.sex}
            {patient.data.phone ? `. Phone: ${patient.data.phone}` : ""}
          </p>
        ) : (
          <p>Loading...</p>
        )}
      </section>

      <section className="grid gap-1">
        <h2 className="mb-0 text-lg">Reason for referral</h2>
        <p className="whitespace-pre-wrap">{letter.reason}</p>
      </section>

      <section className="grid gap-1">
        <h2 className="mb-0 text-lg">Allergies</h2>
        {activeAllergies.length === 0 ? (
          <p>None recorded (not confirmed as no known allergies).</p>
        ) : (
          <ul className="list-disc pl-6">
            {activeAllergies.map((row) => (
              <li key={row.id}>
                {row.substance}
                {row.reaction ? `: ${row.reaction}` : ""} ({SEVERITY_LABELS[row.severity]})
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid gap-1">
        <h2 className="mb-0 text-lg">Medicines prescribed at this visit</h2>
        {activeMedicines.length === 0 ? (
          <p>None.</p>
        ) : (
          <ul className="list-disc pl-6">
            {activeMedicines.map((row) => (
              <li key={row.id}>{describePrescription(row)}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid gap-1">
        <h2 className="mb-0 text-lg">Known problems and diagnoses</h2>
        {activeProblems.length === 0 ? (
          <p>None recorded.</p>
        ) : (
          <ul className="list-disc pl-6">
            {activeProblems.map((row) => (
              <li key={row.id}>
                {row.description}
                {row.code ? ` (${row.code})` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="grid gap-6 pt-4">
        <p>
          Referring clinician: {writer ? `${writer.full_name} (${writer.role})` : "-"}
        </p>
        <p>Signature: ______________________________</p>
      </footer>
    </article>
  );
}
