import { z } from "zod";

// The answer to taking an intake. No reason in it: that is health information.
export const intakeResultSchema = z.object({
  id: z.string().uuid(),
  appointment_id: z.string().uuid(),
  outcome: z.enum(["ready", "escalated"]),
  red_flags: z.array(z.string()),
  recorded_at: z.string(),
  advice: z.string().nullable(), // set when a danger sign sent the patient to in-person care
});
export type IntakeResult = z.infer<typeof intakeResultSchema>;

// For booking screens: has the patient consented, and what did the intake decide?
export const teleconsultStatusSchema = z.object({
  consented: z.boolean(),
  intake: z.enum(["ready", "escalated"]).nullable(),
});
export type TeleconsultStatus = z.infer<typeof teleconsultStatusSchema>;
