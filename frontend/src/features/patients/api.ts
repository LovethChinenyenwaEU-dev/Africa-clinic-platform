import { z } from "zod";

import { ApiError, apiGet, apiPost } from "@/lib/api-client";
import type { NewWrite } from "@/lib/sync/outbox";

import {
  duplicateWarningSchema,
  patientListSchema,
  patientSchema,
  reviewItemSchema,
  type DuplicateMatch,
  type Patient,
  type RegisterPayload,
  type ReviewDecision,
  type ReviewItem,
} from "./schemas";

export const MIN_SEARCH_LENGTH = 2;

/** Search by part of a name or a phone number. Each search is written in the diary. */
export function searchPatients(query: string): Promise<Patient[]> {
  return apiGet(`/patients?q=${encodeURIComponent(query.trim())}`, patientListSchema);
}

/** One patient. Viewing them is written in the diary. */
export function getPatient(patientId: string): Promise<Patient> {
  return apiGet(`/patients/${encodeURIComponent(patientId)}`, patientSchema);
}

export type RegisterResult =
  | { kind: "registered"; patient: Patient }
  | { kind: "possible_duplicate"; matches: DuplicateMatch[] };

/**
 * Register a patient. A possible duplicate is not an error: it is a question for
 * a person, answered by sending the form again with confirmedNotDuplicate.
 */
export async function registerPatient(
  form: RegisterPayload,
  confirmedNotDuplicate = false,
): Promise<RegisterResult> {
  try {
    const patient = await apiPost(
      "/patients",
      { ...form, confirmed_not_duplicate: confirmedNotDuplicate },
      patientSchema,
    );
    return { kind: "registered", patient };
  } catch (error) {
    if (error instanceof ApiError && error.kind === "conflict") {
      const warning = duplicateWarningSchema.safeParse(error.detail);
      if (warning.success) {
        return { kind: "possible_duplicate", matches: warning.data.matches };
      }
    }
    throw error;
  }
}

/**
 * A registration made with no network, for the device outbox. Nobody can answer the
 * duplicate question offline, so the server saves it anyway and, if it looks like
 * someone already registered, flags it for review. The ID is made here, so sending
 * it twice registers one person.
 */
export function offlineRegistrationWrite(form: RegisterPayload): NewWrite {
  return {
    path: "/patients",
    body: { id: crypto.randomUUID(), ...form, registered_offline: true },
    label: "Patient registration",
    encounterId: null,
  };
}

/** Offline registrations that may be someone already registered. Opening it is in the diary. */
export function getReviewQueue(): Promise<ReviewItem[]> {
  return apiGet("/patients/review-queue", z.array(reviewItemSchema));
}

export function decideReview(patientId: string, decision: ReviewDecision): Promise<Patient> {
  return apiPost(`/patients/${encodeURIComponent(patientId)}/review`, decision, patientSchema);
}
