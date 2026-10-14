import { ApiError, apiGet, apiPost } from "@/lib/api-client";

import {
  duplicateWarningSchema,
  patientListSchema,
  patientSchema,
  type DuplicateMatch,
  type Patient,
  type RegisterPayload,
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
