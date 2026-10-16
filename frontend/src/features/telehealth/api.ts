import { apiGet, apiPost } from "@/lib/api-client";

import {
  intakeResultSchema,
  teleconsultStatusSchema,
  type IntakeResult,
  type TeleconsultStatus,
} from "./schemas";

const q = encodeURIComponent;

export function getTeleconsultStatus(appointmentId: string): Promise<TeleconsultStatus> {
  return apiGet(`/teleconsults/${q(appointmentId)}/status`, teleconsultStatusSchema);
}

/**
 * The reason and the danger-sign screen before a remote visit. No danger sign: the
 * patient joins the remote waiting room. A danger sign: in-person care is advised.
 * Sent directly: the answer decides what staff tell the patient now.
 */
export function submitIntake(
  appointmentId: string,
  reason: string,
  redFlags: string[],
): Promise<IntakeResult> {
  return apiPost(
    `/teleconsults/${q(appointmentId)}/intake`,
    { id: crypto.randomUUID(), reason, red_flags: redFlags },
    intakeResultSchema,
  );
}
