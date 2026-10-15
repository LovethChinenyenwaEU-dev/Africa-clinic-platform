import { z } from "zod";

// One diary line. IDs and codes only: never names, notes or anything typed about a patient.
export const auditEventSchema = z.object({
  id: z.string().uuid(),
  actor_id: z.string().uuid(),
  patient_id: z.string().uuid().nullable(),
  entity_id: z.string().uuid().nullable(),
  action: z.string(),
  purpose: z.string().nullable(),
  occurred_at: z.string(),
});
export type AuditEvent = z.infer<typeof auditEventSchema>;

export const staffSchema = z.object({
  id: z.string().uuid(),
  full_name: z.string(),
  role: z.string(),
  is_active: z.boolean(),
});
export type StaffMember = z.infer<typeof staffSchema>;
