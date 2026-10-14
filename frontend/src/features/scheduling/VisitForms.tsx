"use client";

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { PatientPicker } from "@/features/patients/PatientPicker";
import type { Patient } from "@/features/patients/schemas";
import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { lagosInputToIso, todayInLagos } from "@/lib/format";

import { bookVisit, registerWalkIn } from "./api";
import type { Clinician } from "./schemas";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : API_MESSAGES.unavailable;
}

function ClinicianSelect({
  id,
  clinicians,
  value,
  onChange,
  optional,
}: {
  id: string;
  clinicians: Clinician[];
  value: string;
  onChange: (value: string) => void;
  optional: boolean;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>Clinician{optional && " (optional)"}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{optional ? "Whoever is free" : "Choose..."}</option>
        {clinicians.map((person) => (
          <option key={person.id} value={person.id}>
            {person.full_name} ({person.role === "doctor" ? "Doctor" : "Nurse"})
          </option>
        ))}
      </select>
    </div>
  );
}

/** A patient who has arrived without a booking joins the waiting line. */
export function WalkInForm({
  branchId,
  clinicians,
  onDone,
  onCancel,
}: {
  branchId: string;
  clinicians: Clinician[];
  onDone: () => void;
  onCancel: () => void;
}) {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [clinicianId, setClinicianId] = useState("");
  const [missing, setMissing] = useState(false);
  const save = useMutation({ mutationFn: registerWalkIn, onSuccess: onDone });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patient) {
      setMissing(true);
      return;
    }
    save.mutate({ patient_id: patient.id, branch_id: branchId, clinician_id: clinicianId || null });
  }

  return (
    <form className="card" onSubmit={handleSubmit} noValidate aria-labelledby="walk-in-heading">
      <h2 id="walk-in-heading" className="mb-0">
        Walk-in
      </h2>
      <PatientPicker
        chosen={patient}
        onChoose={(choice) => {
          setPatient(choice);
          setMissing(false);
        }}
      />
      {missing && <p className="error">Choose the patient first.</p>}
      <ClinicianSelect
        id="walk-in-clinician"
        clinicians={clinicians}
        value={clinicianId}
        onChange={setClinicianId}
        optional
      />
      {save.isError && (
        <p role="alert" className="error">
          {messageOf(save.error)}
        </p>
      )}
      <div className="flex gap-3">
        <button className="button" type="submit" disabled={save.isPending}>
          {save.isPending ? "Adding..." : "Add to the queue"}
        </button>
        <button className="button-secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

/** Book a visit ahead of time, at a Lagos date and time. */
export function BookVisitForm({
  branchId,
  clinicians,
  onDone,
  onCancel,
}: {
  branchId: string;
  clinicians: Clinician[];
  onDone: () => void;
  onCancel: () => void;
}) {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [clinicianId, setClinicianId] = useState("");
  const [when, setWhen] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const save = useMutation({ mutationFn: bookVisit, onSuccess: onDone });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patient) return setProblem("Choose the patient first.");
    if (!clinicianId) return setProblem("Choose the clinician.");
    if (!when) return setProblem("Choose the date and time.");
    setProblem(null);
    save.mutate({
      patient_id: patient.id,
      branch_id: branchId,
      clinician_id: clinicianId,
      starts_at: lagosInputToIso(when),
    });
  }

  return (
    <form className="card" onSubmit={handleSubmit} noValidate aria-labelledby="book-heading">
      <h2 id="book-heading" className="mb-0">
        Book a visit
      </h2>
      <PatientPicker chosen={patient} onChoose={setPatient} />
      <ClinicianSelect
        id="book-clinician"
        clinicians={clinicians}
        value={clinicianId}
        onChange={setClinicianId}
        optional={false}
      />
      <div className="field">
        <label htmlFor="book-when">Date and time (Lagos time)</label>
        <input
          id="book-when"
          type="datetime-local"
          min={`${todayInLagos()}T00:00`}
          step={300}
          value={when}
          onChange={(event) => setWhen(event.target.value)}
        />
      </div>
      {problem && <p className="error">{problem}</p>}
      {save.isError && (
        <p role="alert" className="error">
          {messageOf(save.error)}
        </p>
      )}
      <div className="flex gap-3">
        <button className="button" type="submit" disabled={save.isPending}>
          {save.isPending ? "Booking..." : "Book"}
        </button>
        <button className="button-secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
