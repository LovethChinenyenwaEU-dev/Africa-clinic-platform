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
