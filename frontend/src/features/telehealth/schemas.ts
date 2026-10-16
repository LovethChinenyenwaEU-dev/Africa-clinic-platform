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

export const CONSULT_MODES = ["video", "audio", "text"] as const;
export type ConsultMode = (typeof CONSULT_MODES)[number];

export const roomSchema = z.object({
  appointment_id: z.string().uuid(),
  provider: z.string(),
  mode: z.enum(CONSULT_MODES),
  video_url: z.string().nullable(),
  audio_url: z.string().nullable(),
});
export type Room = z.infer<typeof roomSchema>;

export const messageSchema = z.object({
  id: z.string().uuid(),
  sender: z.string(), // staff or patient
  sender_staff_id: z.string().uuid().nullable(),
  body: z.string(),
  sent_at: z.string(),
});
export type Message = z.infer<typeof messageSchema>;
