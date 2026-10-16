"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { PatientPicker } from "@/features/patients/PatientPicker";
import type { Patient } from "@/features/patients/schemas";
import { API_MESSAGES, ApiError } from "@/lib/api-client";
import { formatDateTime, lagosInputToIso, todayInLagos } from "@/lib/format";

import { bookVisit, getFreeSlots, registerWalkIn } from "./api";
import { VISIT_TYPE_LABELS } from "./labels";
import type { Clinician, Slot } from "./schemas";

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

// How many free slots the form offers at once; a later time can still be typed by hand.
const SLOTS_SHOWN = 12;

/** Book a visit ahead of time: pick a free slot, or type a Lagos date and time. */
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
  const [visitType, setVisitType] = useState<"in_person" | "teleconsult">("in_person");
  const [slot, setSlot] = useState<Slot | null>(null);
  const [when, setWhen] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const save = useMutation({ mutationFn: bookVisit, onSuccess: onDone });

  // The clinician's free slots from their published hours, this week.
  const slots = useQuery({
    queryKey: ["free-slots", clinicianId, visitType],
    queryFn: () => getFreeSlots(clinicianId, visitType, todayInLagos()),
    enabled: clinicianId !== "",
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patient) return setProblem("Choose the patient first.");
    if (!clinicianId) return setProblem("Choose the clinician.");
    if (!slot && !when) return setProblem("Choose a free slot, or a date and time.");
    setProblem(null);
    save.mutate({
      patient_id: patient.id,
      branch_id: branchId,
      clinician_id: clinicianId,
      visit_type: visitType,
      ...(slot
        ? { starts_at: slot.starts_at, duration_minutes: slotMinutes(slot) }
        : { starts_at: lagosInputToIso(when) }),
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
        onChange={(value) => {
          setClinicianId(value);
          setSlot(null);
        }}
        optional={false}
      />
      <fieldset className="field">
        <legend className="font-semibold">Kind of visit</legend>
        <div className="flex flex-wrap gap-4">
          {(["in_person", "teleconsult"] as const).map((kind) => (
            <label key={kind} className="flex items-center gap-2 font-normal">
              <input
                type="radio"
                name="book-visit-type"
                checked={visitType === kind}
                onChange={() => {
                  setVisitType(kind);
                  setSlot(null);
                }}
              />
              {VISIT_TYPE_LABELS[kind]}
            </label>
          ))}
        </div>
      </fieldset>

      {clinicianId && (
        <div className="field">
          <span className="font-semibold">Free slots this week</span>
          {slots.isPending && <p className="text-sm">Loading free slots...</p>}
          {slots.isError && <p className="error">{messageOf(slots.error)}</p>}
          {slots.data?.length === 0 && (
            <p className="text-sm">
              No free {VISIT_TYPE_LABELS[visitType].toLowerCase()} slots published this week.
              You can still type a date and time below.
            </p>
          )}
          {slots.data && slots.data.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {slots.data.slice(0, SLOTS_SHOWN).map((free) => (
                <button
                  key={free.starts_at}
                  type="button"
                  aria-pressed={slot?.starts_at === free.starts_at}
                  className={slot?.starts_at === free.starts_at ? "button" : "button-secondary"}
                  onClick={() => {
                    setSlot(free);
                    setWhen("");
                  }}
                >
                  {formatDateTime(free.starts_at)}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="field">
        <label htmlFor="book-when">Or another date and time (Lagos time)</label>
        <input
          id="book-when"
          type="datetime-local"
          min={`${todayInLagos()}T00:00`}
          step={300}
          value={when}
          onChange={(event) => {
            setWhen(event.target.value);
            setSlot(null);
          }}
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

/** A slot's length in minutes, so the visit books exactly that slot. */
export function slotMinutes(slot: Pick<Slot, "starts_at" | "ends_at">): number {
  return Math.round((Date.parse(slot.ends_at) - Date.parse(slot.starts_at)) / 60_000);
}
