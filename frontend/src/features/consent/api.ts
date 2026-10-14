import { ApiError, apiGet, apiPost } from "@/lib/api-client";

import {
  consentHistorySchema,
  consentSchema,
  wordingSchema,
  type Consent,
  type GrantedBy,
  type Purpose,
  type Wording,
} from "./schemas";

const base = (patientId: string) => `/patients/${encodeURIComponent(patientId)}/consents`;

/** Every consent this patient has given or withdrawn. Viewing it is written in the diary. */
export function getConsentHistory(patientId: string): Promise<Consent[]> {
  return apiGet(base(patientId), consentHistorySchema);
}

/** The clinic's current wording for a purpose, or null if none has been published yet. */
export async function getCurrentWording(purpose: Purpose): Promise<Wording | null> {
  try {
    return await apiGet(
      `/consent/texts/current?purpose=${encodeURIComponent(purpose)}`,
      wordingSchema,
    );
  } catch (error) {
    if (error instanceof ApiError && error.kind === "not_found") return null;
    throw error;
  }
}

/** Record that the patient (or a caregiver) agreed to the clinic's current wording. */
export function recordConsent(
  patientId: string,
  purpose: Purpose,
  grantedBy: GrantedBy,
): Promise<Consent> {
  return apiPost(base(patientId), { purpose, granted_by: grantedBy }, consentSchema);
}

/** Take the agreement back. The record stays, stamped with when it was withdrawn. */
export function withdrawConsent(patientId: string, purpose: Purpose): Promise<Consent> {
  return apiPost(`${base(patientId)}/${encodeURIComponent(purpose)}/revoke`, {}, consentSchema);
}
