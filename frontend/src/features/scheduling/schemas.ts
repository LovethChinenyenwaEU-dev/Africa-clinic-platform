import { z } from "zod";

export const branchSchema = z.object({ id: z.string().uuid(), name: z.string(), city: z.string() });
export type Branch = z.infer<typeof branchSchema>;

export const clinicianSchema = z.object({
  id: z.string().uuid(),
  full_name: z.string(),
  role: z.string(),
});
export type Clinician = z.infer<typeof clinicianSchema>;

export const queueEntrySchema = z.object({
  appointment_id: z.string().uuid(),
  patient_id: z.string().uuid(),
  patient_name: z.string(),
  clinician_id: z.string().uuid().nullable(),
  kind: z.string(),
  visit_type: z.string(),
  status: z.string(),
  position: z.number().int().nullable(),
  scheduled_at: z.string(),
  checked_in_at: z.string().nullable(),
  consult_started_at: z.string().nullable(),
  from_earlier_day: z.boolean(),
  triage_level: z.string().nullable().default(null), // None until a clinician triages
  red_flags: z.array(z.string()).default([]), // empty for staff without clinical access
});
export type QueueEntry = z.infer<typeof queueEntrySchema>;

export const dayEntrySchema = z.object({
  appointment_id: z.string().uuid(),
  patient_id: z.string().uuid(),
  patient_name: z.string(),
  clinician_id: z.string().uuid().nullable(),
  kind: z.string(),
  visit_type: z.string(),
  status: z.string(),
  starts_at: z.string(),
  ends_at: z.string(),
  checked_in_at: z.string().nullable(),
});
export type DayEntry = z.infer<typeof dayEntrySchema>;

export const appointmentSchema = z.object({
  id: z.string().uuid(),
  patient_id: z.string().uuid(),
  status: z.string(),
  starts_at: z.string(),
});
export type Appointment = z.infer<typeof appointmentSchema>;

export const triageSchema = z.object({
  id: z.string().uuid(),
  appointment_id: z.string().uuid(),
  level: z.string(),
  red_flags: z.array(z.string()),
  recorded_by_id: z.string().uuid(),
  recorded_at: z.string(),
});
export type Triage = z.infer<typeof triageSchema>;

// A clinician's weekly hours (Week 9). Times are Lagos clock times, "09:00:00".
export const hoursSchema = z.object({
  id: z.string().uuid(),
  clinician_id: z.string().uuid(),
  branch_id: z.string().uuid(),
  weekday: z.number().int().min(0).max(6), // 0 Monday ... 6 Sunday
  starts: z.string(),
  ends: z.string(),
  visit_type: z.string(),
  slot_minutes: z.number().int(),
});
export type Hours = z.infer<typeof hoursSchema>;

export const slotSchema = z.object({
  starts_at: z.string(),
  ends_at: z.string(),
  branch_id: z.string().uuid(),
  visit_type: z.string(),
});
export type Slot = z.infer<typeof slotSchema>;
