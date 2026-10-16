import { z } from "zod";

import { ApiError, apiGet, apiPost } from "@/lib/api-client";
import type { NewWrite } from "@/lib/sync/outbox";

import {
  allergySchema,
  encounterSchema,
  noteSchema,
  problemSchema,
  vitalsSchema,
  type Allergy,
  type Encounter,
  type Note,
  type Problem,
  type ReadingField,
  type Vitals,
} from "./schemas";

/*
 * Every new entry carries an ID made here, on the device. If the same request is
 * sent twice (a double tap, a retry), the backend recognises the ID and creates
 * nothing new.
 *
 * Clinical entries (vitals, allergies, problems, notes) are not sent from here:
 * the functions below describe the write, and the screen queues it in the device
 * outbox, which sends it now or when the network returns (Week 8). Opening and
 * signing off an encounter stay online-only on purpose.
 */
const newId = () => crypto.randomUUID();
const q = encodeURIComponent;
const withHistory = (include: boolean) => (include ? "?include_history=true" : "");

// Starting a visit

/** Start the consultation, then open its encounter. Returns the encounter. */
export async function startVisit(appointmentId: string, patientId: string): Promise<Encounter> {
  await apiPost(`/appointments/${q(appointmentId)}/start`, {}, z.unknown());
  return openRecord(appointmentId, patientId);
}

/** Open (or find again) the encounter of a visit already with a clinician. */
export function openRecord(appointmentId: string, patientId: string): Promise<Encounter> {
  return apiPost(
    "/encounters",
    { id: newId(), patient_id: patientId, appointment_id: appointmentId },
    encounterSchema,
  );
}

// The encounter

export function getEncounter(encounterId: string): Promise<Encounter> {
  return apiGet(`/encounters/${q(encounterId)}`, encounterSchema);
}

export type SignOffResult = { visitCompleted: boolean };

/**
 * Close the encounter, then complete its visit. The visit can only be completed by
 * whoever started it; if that was someone else, it stays open for them.
 */
export async function signOff(encounter: Encounter): Promise<SignOffResult> {
  await apiPost(`/encounters/${q(encounter.id)}/close`, {}, encounterSchema);
  if (!encounter.appointment_id) return { visitCompleted: false };
  try {
    await apiPost(`/appointments/${q(encounter.appointment_id)}/complete`, {}, z.unknown());
    return { visitCompleted: true };
  } catch (error) {
    // Already completed, or started by another clinician: the record is still signed off.
    if (error instanceof ApiError && (error.kind === "conflict" || error.kind === "forbidden")) {
      return { visitCompleted: false };
    }
    throw error;
  }
}

export function markOpenedByMistake(encounterId: string): Promise<Encounter> {
  return apiPost(`/encounters/${q(encounterId)}/entered-in-error`, {}, encounterSchema);
}

// Vitals

export type Readings = Partial<Record<ReadingField, number | string>>;

export function getVitals(encounterId: string, includeHistory = false): Promise<Vitals[]> {
  return apiGet(
    `/encounters/${q(encounterId)}/vitals${withHistory(includeHistory)}`,
    z.array(vitalsSchema),
  );
}

/** New vitals, timed by the device: if they reach the server after sign-off, they still count. */
export function vitalsWrite(encounterId: string, readings: Readings, now = new Date()): NewWrite {
  return {
    path: `/encounters/${q(encounterId)}/vitals`,
    body: { id: newId(), measured_at: now.toISOString(), ...readings },
    label: "Vitals",
    encounterId,
  };
}

export function vitalsCorrectionWrite(
  vitalsId: string,
  encounterId: string,
  readings: Readings,
): NewWrite {
  return {
    path: `/vitals/${q(vitalsId)}/corrections`,
    body: { id: newId(), ...readings },
    label: "Vitals correction",
    encounterId,
  };
}

// Allergies and problems (the patient's lists)

export type AllergyDetails = {
  substance: string;
  reaction: string | null;
  severity: string;
  clinical_status: string;
};

export function getAllergies(patientId: string): Promise<Allergy[]> {
  return apiGet(`/patients/${q(patientId)}/allergies`, z.array(allergySchema));
}

export function allergyWrite(encounterId: string, details: AllergyDetails): NewWrite {
  return {
    path: `/encounters/${q(encounterId)}/allergies`,
    body: { id: newId(), ...details },
    label: "Allergy",
    encounterId,
  };
}

export function allergyRevisionWrite(
  allergyId: string,
  encounterId: string,
  details: AllergyDetails,
): NewWrite {
  return {
    path: `/allergies/${q(allergyId)}/revisions`,
    body: { id: newId(), encounter_id: encounterId, ...details },
    label: "Allergy change",
    encounterId,
  };
}

export type ProblemDetails = {
  description: string;
  category: string;
  code: string | null;
  clinical_status: string;
  onset_date: string | null;
};

export function getProblems(patientId: string): Promise<Problem[]> {
  return apiGet(`/patients/${q(patientId)}/problems`, z.array(problemSchema));
}

export function problemWrite(encounterId: string, details: ProblemDetails): NewWrite {
  return {
    path: `/encounters/${q(encounterId)}/problems`,
    body: { id: newId(), ...details },
    label: "Problem or diagnosis",
    encounterId,
  };
}

export function problemRevisionWrite(
  problemId: string,
  encounterId: string,
  details: ProblemDetails,
): NewWrite {
  return {
    path: `/problems/${q(problemId)}/revisions`,
    body: { id: newId(), encounter_id: encounterId, ...details },
    label: "Problem change",
    encounterId,
  };
}

// Notes

export function getNotes(encounterId: string, includeHistory = false): Promise<Note[]> {
  return apiGet(
    `/encounters/${q(encounterId)}/notes${withHistory(includeHistory)}`,
    z.array(noteSchema),
  );
}

/** A new note, timed by the device: if it reaches the server after sign-off, it still counts. */
export function noteWrite(
  encounterId: string,
  kind: string,
  body: string,
  now = new Date(),
): NewWrite {
  return {
    path: `/encounters/${q(encounterId)}/notes`,
    body: { id: newId(), kind, body, written_at: now.toISOString() },
    label: "Note",
    encounterId,
  };
}

export function noteAmendmentWrite(noteId: string, encounterId: string, body: string): NewWrite {
  return {
    path: `/notes/${q(noteId)}/amendments`,
    body: { id: newId(), body },
    label: "Note amendment",
    encounterId,
  };
}

// Conflicts (two devices changed the same thing; Week 8)

export type ConflictKind = "vitals" | "notes" | "allergies" | "problems";
export type Keep = "this" | "current";

/**
 * Settle a conflict: keep this version, or the one currently in use. The other goes
 * to history; nothing is deleted. Sent directly, not through the outbox: the choice
 * is made against what the server holds now.
 */
export async function resolveConflict(kind: ConflictKind, id: string, keep: Keep): Promise<void> {
  await apiPost(`/${kind}/${q(id)}/resolve`, { keep }, z.unknown());
}
