import type { GrantedBy, Purpose } from "./schemas";

export const PURPOSE_LABELS: Record<Purpose, string> = {
  treatment: "Treatment",
  reminders: "SMS/WhatsApp reminders",
  teleconsult: "Online consultations",
  referral_sharing: "Sharing records on referral",
};

export const GRANTED_BY_LABELS: Record<GrantedBy, string> = {
  patient: "the patient",
  caregiver: "a caregiver",
};
