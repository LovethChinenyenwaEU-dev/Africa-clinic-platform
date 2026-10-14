import { z } from "zod";

// The purposes the backend knows (backend/app/modules/consent/models.py).
export const PURPOSES = ["treatment", "reminders", "teleconsult", "referral_sharing"] as const;
export type Purpose = (typeof PURPOSES)[number];

export const GRANTED_BY = ["patient", "caregiver"] as const;
export type GrantedBy = (typeof GRANTED_BY)[number];

export const consentSchema = z.object({
  id: z.string().uuid(),
  patient_id: z.string().uuid(),
  purpose: z.string(),
  wording_version: z.number().int(),
  granted_by: z.string(),
  granted_at: z.string(),
  revoked_at: z.string().nullable(),
});
export type Consent = z.infer<typeof consentSchema>;

export const consentHistorySchema = z.array(consentSchema);

export const wordingSchema = z.object({
  id: z.string().uuid(),
  purpose: z.string(),
  version: z.number().int(),
  body: z.string(),
  created_at: z.string(),
});
export type Wording = z.infer<typeof wordingSchema>;
