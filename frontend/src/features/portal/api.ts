import { z } from "zod";

import { ApiError, patientGet, patientPost } from "@/lib/api-client";

/*
 * The patient's own pages (Week 9). Signing in goes through /api/patient-session,
 * which keeps the token in an httpOnly cookie; everything else through /api/patient.
 */

export const meSchema = z.object({ full_name: z.string() });

export const myVisitSchema = z.object({
  appointment_id: z.string().uuid(),
  starts_at: z.string(),
  ends_at: z.string(),
  visit_type: z.string(),
  status: z.string(),
  clinician_name: z.string().nullable(),
});
export type MyVisit = z.infer<typeof myVisitSchema>;

export const mySummarySchema = z.object({
  id: z.string().uuid(),
  body: z.string(),
  approved_at: z.string().nullable(),
});
export type MySummary = z.infer<typeof mySummarySchema>;

export type SignInDetails = { clinic_id: string; phone: string; date_of_birth: string };

const startAnswer = z.object({ message: z.string(), development_code: z.string().nullable() });
export type StartAnswer = z.infer<typeof startAnswer>;

async function session<T>(body: unknown, schema: z.ZodType<T>, method = "POST"): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api/patient-session", {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    });
  } catch {
    throw new ApiError("unavailable");
  }
  const data: unknown = await response.json().catch(() => null);
  const message =
    data && typeof data === "object" && typeof (data as { message?: unknown }).message === "string"
      ? (data as { message: string }).message
      : undefined;
  if (response.status === 401) throw new ApiError("signed_out", message);
  if (response.status === 422) throw new ApiError("invalid", message);
  if (!response.ok) throw new ApiError("unavailable", message);
  const parsed = schema.safeParse(data);
  if (!parsed.success) throw new ApiError("unavailable");
  return parsed.data;
}

/** Ask for a code by SMS. The answer is the same whether or not the details matched. */
export function requestCode(details: SignInDetails): Promise<StartAnswer> {
  return session({ step: "start", ...details }, startAnswer);
}

/** Check the code. On success the patient cookie is set by the server. */
export async function confirmCode(details: SignInDetails, code: string): Promise<void> {
  await session({ step: "finish", ...details, code }, z.object({ ok: z.literal(true) }));
}

export async function signOutPatient(): Promise<void> {
  await session({}, z.object({ ok: z.literal(true) }), "DELETE");
}

export function getMe() {
  return patientGet("/me", meSchema);
}

export function getMyVisits(): Promise<MyVisit[]> {
  return patientGet("/visits", z.array(myVisitSchema));
}

export function getMySummaries(): Promise<MySummary[]> {
  return patientGet("/summaries", z.array(mySummarySchema));
}

/** Split visits into those still to come and those already past, as the server ordered them. */
export function splitVisits(visits: MyVisit[], now: Date = new Date()) {
  const upcoming = visits.filter((visit) => new Date(visit.ends_at) >= now);
  const past = visits.filter((visit) => new Date(visit.ends_at) < now);
  return { upcoming, past };
}

// Remote care, done by the patient (Week 9 Step 8b)

const consentSchema = z.object({
  consented: z.boolean(),
  wording: z.string().nullable(),
  version: z.number().nullable(),
});
export type RemoteCareConsent = z.infer<typeof consentSchema>;

export const remoteSlotSchema = z.object({
  clinician_id: z.string().uuid(),
  clinician_name: z.string(),
  starts_at: z.string(),
  ends_at: z.string(),
});
export type RemoteSlot = z.infer<typeof remoteSlotSchema>;

const intakeAnswerSchema = z.object({
  outcome: z.enum(["ready", "escalated"]),
  advice: z.string().nullable(),
});
export type IntakeAnswer = z.infer<typeof intakeAnswerSchema>;

const roomSchema = z.object({
  mode: z.enum(["video", "audio", "text"]),
  video_url: z.string().nullable(),
  audio_url: z.string().nullable(),
});
export type PatientRoom = z.infer<typeof roomSchema>;

export const chatMessageSchema = z.object({
  id: z.string().uuid(),
  sender: z.string(), // patient or staff
  body: z.string(),
  sent_at: z.string(),
});
export type ChatMessage = z.infer<typeof chatMessageSchema>;

const q = encodeURIComponent;

export function getRemoteCareConsent(): Promise<RemoteCareConsent> {
  return patientGet("/remote-care/consent", consentSchema);
}

export function agreeToRemoteCare(): Promise<RemoteCareConsent> {
  return patientPost("/remote-care/consent", {}, consentSchema);
}

export function getRemoteSlots(fromDay: string): Promise<RemoteSlot[]> {
  return patientGet(`/remote-slots?from_day=${q(fromDay)}`, z.array(remoteSlotSchema));
}

export function bookRemoteVisit(slot: RemoteSlot): Promise<MyVisit> {
  return patientPost(
    "/visits",
    { id: crypto.randomUUID(), clinician_id: slot.clinician_id, starts_at: slot.starts_at },
    myVisitSchema,
  );
}

export function answerIntake(
  visitId: string,
  reason: string,
  redFlags: string[],
): Promise<IntakeAnswer> {
  return patientPost(
    `/visits/${q(visitId)}/intake`,
    { id: crypto.randomUUID(), reason, red_flags: redFlags },
    intakeAnswerSchema,
  );
}

export function getMyRoom(visitId: string): Promise<PatientRoom> {
  return patientGet(`/visits/${q(visitId)}/room`, roomSchema);
}

export function getMyChat(visitId: string, since?: string): Promise<ChatMessage[]> {
  const query = since ? `?since=${q(since)}` : "";
  return patientGet(`/visits/${q(visitId)}/messages${query}`, z.array(chatMessageSchema));
}

export function sendMyMessage(visitId: string, body: string): Promise<ChatMessage> {
  return patientPost(
    `/visits/${q(visitId)}/messages`,
    { id: crypto.randomUUID(), body },
    chatMessageSchema,
  );
}

/** A remote visit's next step on the patient page. */
export function remoteStep(visit: MyVisit): "intake" | "waiting" | "in_consult" | null {
  if (visit.visit_type !== "teleconsult") return null;
  if (visit.status === "booked") return "intake";
  if (visit.status === "waiting") return "waiting";
  if (visit.status === "in_consult") return "in_consult";
  return null;
}
