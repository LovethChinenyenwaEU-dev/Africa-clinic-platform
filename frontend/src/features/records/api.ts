import { z } from "zod";

import { ApiError, apiGet, apiPost } from "@/lib/api-client";

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
 * nothing new. Offline sync (Week 8) relies on the same rule.
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

export function recordVitals(encounterId: string, readings: Readings): Promise<Vitals> {
  return apiPost(
    `/encounters/${q(encounterId)}/vitals`,
    { id: newId(), ...readings },
    vitalsSchema,
  );
}

export function correctVitals(vitalsId: string, readings: Readings): Promise<Vitals> {
  return apiPost(
    `/vitals/${q(vitalsId)}/corrections`,
    { id: newId(), ...readings },
    vitalsSchema,
  );
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

export function addAllergy(encounterId: string, details: AllergyDetails): Promise<Allergy> {
  return apiPost(
    `/encounters/${q(encounterId)}/allergies`,
    { id: newId(), ...details },
    allergySchema,
  );
}

export function reviseAllergy(
  allergyId: string,
  encounterId: string,
  details: AllergyDetails,
): Promise<Allergy> {
  return apiPost(
    `/allergies/${q(allergyId)}/revisions`,
    { id: newId(), encounter_id: encounterId, ...details },
    allergySchema,
  );
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

export function addProblem(encounterId: string, details: ProblemDetails): Promise<Problem> {
  return apiPost(
    `/encounters/${q(encounterId)}/problems`,
    { id: newId(), ...details },
    problemSchema,
  );
}

export function reviseProblem(
  problemId: string,
  encounterId: string,
  details: ProblemDetails,
): Promise<Problem> {
  return apiPost(
    `/problems/${q(problemId)}/revisions`,
    { id: newId(), encounter_id: encounterId, ...details },
    problemSchema,
  );
}

// Notes

export function getNotes(encounterId: string, includeHistory = false): Promise<Note[]> {
  return apiGet(
    `/encounters/${q(encounterId)}/notes${withHistory(includeHistory)}`,
    z.array(noteSchema),
  );
}

export function writeNote(encounterId: string, kind: string, body: string): Promise<Note> {
  return apiPost(`/encounters/${q(encounterId)}/notes`, { id: newId(), kind, body }, noteSchema);
}

export function amendNote(noteId: string, body: string): Promise<Note> {
  return apiPost(`/notes/${q(noteId)}/amendments`, { id: newId(), body }, noteSchema);
}
