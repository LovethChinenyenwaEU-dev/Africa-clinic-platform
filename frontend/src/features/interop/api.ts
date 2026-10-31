import { z } from "zod";

import { apiGet } from "@/lib/api-client";

/*
 * A patient's record as an HL7 FHIR R4 bundle (Week 11, FR-I1). The backend builds it;
 * the screen only checks it is a bundle and saves it as a file.
 */

export type ExportReason = "patient_request" | "referral" | "transfer";

export const REASONS: { value: ExportReason; label: string; hint: string }[] = [
  {
    value: "patient_request",
    label: "The patient asked for a copy",
    hint: "Their own record, which they have a right to.",
  },
  {
    value: "referral",
    label: "For a referral",
    hint: "To the provider the patient is referred to. Needs their consent to sharing.",
  },
  {
    value: "transfer",
    label: "The patient is moving to another provider",
    hint: "Needs their consent to sharing.",
  },
];

const bundleSchema = z
  .object({
    resourceType: z.literal("Bundle"),
    type: z.literal("collection"),
    entry: z.array(z.object({ fullUrl: z.string(), resource: z.record(z.string(), z.unknown()) })),
  })
  .loose(); // the resources carry many more fields; only the outline is checked
export type FhirBundle = z.infer<typeof bundleSchema>;

export function exportRecord(patientId: string, reason: ExportReason): Promise<FhirBundle> {
  const q = encodeURIComponent;
  return apiGet(`/interop/patients/${q(patientId)}/fhir?reason=${q(reason)}`, bundleSchema);
}

/** The file name says what it is, never who: a name in a downloads folder is a leak. */
export function exportFileName(patientId: string, today: string): string {
  return `patient-record-${patientId.slice(0, 8)}-${today}.fhir.json`;
}

/** How many of each resource, for the message after the download. */
export function countResources(bundle: FhirBundle): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const { resource } of bundle.entry) {
    const kind = String(resource.resourceType);
    counts[kind] = (counts[kind] ?? 0) + 1;
  }
  return counts;
}
