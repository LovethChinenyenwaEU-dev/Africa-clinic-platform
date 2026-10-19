import { z } from "zod";

const id = z.string().uuid();
// Exact decimals arrive as text ("38.4") so no precision is lost on the way.
const decimal = z.string().nullable();

export const encounterSchema = z.object({
  id,
  patient_id: id,
  appointment_id: id.nullable(),
  clinician_id: id,
  status: z.string(),
  opened_at: z.string(),
  closed_at: z.string().nullable(),
  closed_by_id: id.nullable(),
});
export type Encounter = z.infer<typeof encounterSchema>;

export const vitalsSchema = z.object({
  id,
  encounter_id: id,
  patient_id: id,
  status: z.string(), // current, superseded or conflict
  replaces_id: id.nullable(),
  systolic_mmhg: z.number().int().nullable(),
  diastolic_mmhg: z.number().int().nullable(),
  pulse_bpm: z.number().int().nullable(),
  respiratory_rate: z.number().int().nullable(),
  spo2_pct: z.number().int().nullable(),
  temperature_c: decimal,
  weight_kg: decimal,
  height_cm: decimal,
  measured_at: z.string(),
  recorded_by_id: id,
  recorded_at: z.string(),
  synced_late: z.boolean().default(false), // taken offline before sign-off, arrived after
});
export type Vitals = z.infer<typeof vitalsSchema>;

export const READING_FIELDS = [
  "systolic_mmhg",
  "diastolic_mmhg",
  "pulse_bpm",
  "respiratory_rate",
  "spo2_pct",
  "temperature_c",
  "weight_kg",
  "height_cm",
] as const;
export type ReadingField = (typeof READING_FIELDS)[number];

export const allergySchema = z.object({
  id,
  patient_id: id,
  encounter_id: id,
  version_status: z.string(),
  replaces_id: id.nullable(),
  substance: z.string(),
  reaction: z.string().nullable(),
  severity: z.string(),
  clinical_status: z.string(),
  recorded_by_id: id,
  recorded_at: z.string(),
});
export type Allergy = z.infer<typeof allergySchema>;

export const problemSchema = z.object({
  id,
  patient_id: id,
  encounter_id: id,
  version_status: z.string(),
  replaces_id: id.nullable(),
  category: z.string(),
  description: z.string(),
  code: z.string().nullable(),
  clinical_status: z.string(),
  onset_date: z.string().nullable(),
  recorded_by_id: id,
  recorded_at: z.string(),
});
export type Problem = z.infer<typeof problemSchema>;

export const noteSchema = z.object({
  id,
  encounter_id: id,
  patient_id: id,
  version_status: z.string(),
  replaces_id: id.nullable(),
  kind: z.string(),
  body: z.string(),
  recorded_by_id: id,
  recorded_at: z.string(),
  written_at: z.string().optional(), // when written on the device
  synced_late: z.boolean().default(false), // written offline before sign-off, arrived after
});
export type Note = z.infer<typeof noteSchema>;

export const prescriptionSchema = z.object({
  id,
  encounter_id: id,
  patient_id: id,
  version_status: z.string(), // current, superseded or conflict
  replaces_id: id.nullable(),
  medicine: z.string(),
  strength: z.string().nullable(),
  dose: z.string(),
  route: z.string(),
  frequency: z.string(),
  duration: z.string(),
  instructions: z.string().nullable(),
  clinical_status: z.string(), // active, stopped or entered_in_error
  recorded_by_id: id,
  recorded_at: z.string(),
  written_at: z.string(),
  synced_late: z.boolean().default(false),
});
export type Prescription = z.infer<typeof prescriptionSchema>;

export const followUpSchema = z.object({
  id,
  encounter_id: id,
  patient_id: id,
  due_date: z.string(), // a Lagos day, "2026-11-16"
  visit_type: z.string(),
  instructions: z.string().nullable(),
  status: z.string(), // planned, booked or cancelled
  appointment_id: id.nullable(),
  recorded_by_id: id,
  recorded_at: z.string(),
  synced_late: z.boolean().default(false),
});
export type FollowUp = z.infer<typeof followUpSchema>;

export const referralSchema = z.object({
  id,
  encounter_id: id,
  patient_id: id,
  to_name: z.string(),
  specialty: z.string().nullable(),
  urgency: z.string(), // routine, urgent or emergency
  reason: z.string(),
  status: z.string(), // active or cancelled
  recorded_by_id: id,
  recorded_at: z.string(),
  written_at: z.string(),
  synced_late: z.boolean().default(false),
});
export type Referral = z.infer<typeof referralSchema>;

export const summarySchema = z.object({
  id,
  encounter_id: id,
  patient_id: id,
  body: z.string(),
  status: z.enum(["draft", "approved", "withdrawn"]),
  drafted_by_id: id,
  drafted_at: z.string(),
  updated_at: z.string(),
  approved_by_id: id.nullable(),
  approved_at: z.string().nullable(),
  withdrawn_by_id: id.nullable(),
  withdrawn_at: z.string().nullable(),
});
export type Summary = z.infer<typeof summarySchema>;
