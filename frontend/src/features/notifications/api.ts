import { z } from "zod";

import { apiGet, apiPost } from "@/lib/api-client";

/*
 * The notification console (Week 11), for admins: what the reminder worker did. IDs,
 * codes and times only, never a patient's name or phone.
 */

export const MAX_DAYS = 31; // the backend's limit

export const REMINDER_STATUSES = ["pending", "sent", "failed", "cancelled"] as const;
export type ReminderStatus = (typeof REMINDER_STATUSES)[number];

export const STATUS_LABELS: Record<ReminderStatus, string> = {
  pending: "Waiting to send",
  sent: "Sent",
  failed: "Failed",
  cancelled: "Not needed",
};

// The worker's reasons, in words an admin can act on (backend notifications/sender.py).
export const REASON_LABELS: Record<string, string> = {
  no_phone: "No phone number on the patient's record",
  no_consent: "The patient has not agreed to reminders",
  provider_unavailable: "The SMS provider could not be reached",
  provider_rejected: "The SMS provider refused the message",
  visit_not_upcoming: "The visit was cancelled, moved on or already started",
};

export function describeReason(code: string | null): string {
  if (!code) return "";
  return REASON_LABELS[code] ?? code;
}

export const CHANNEL_LABELS: Record<string, string> = { sms: "SMS", whatsapp: "WhatsApp" };

const lineSchema = z.object({
  id: z.string().uuid(),
  appointment_id: z.string().uuid(),
  channel: z.string(),
  status: z.enum(REMINDER_STATUSES),
  due_at: z.string(),
  attempts: z.number().int().nonnegative(),
  last_error: z.string().nullable(),
  sent_at: z.string().nullable(),
  visit_starts_at: z.string().nullable(),
  visit_type: z.string().nullable(),
  can_retry: z.boolean(),
});
export type ReminderLine = z.infer<typeof lineSchema>;

const consoleSchema = z.object({
  from_day: z.string(),
  to_day: z.string(),
  counts: z.record(z.string(), z.number().int()),
  failures: z.record(z.string(), z.number().int()),
  lines: z.array(lineSchema),
  more: z.boolean(),
});
export type ReminderConsole = z.infer<typeof consoleSchema>;

const q = encodeURIComponent;

export function getReminders(
  fromDay: string,
  toDay: string,
  status: ReminderStatus | null,
): Promise<ReminderConsole> {
  const only = status ? `&reminder_status=${q(status)}` : "";
  return apiGet(
    `/notifications/reminders?from_day=${q(fromDay)}&to_day=${q(toDay)}${only}`,
    consoleSchema,
  );
}

export async function retryReminder(id: string): Promise<void> {
  await apiPost(
    `/notifications/reminders/${q(id)}/retry`,
    {},
    z.object({ id: z.string(), status: z.string() }).loose(),
  );
}
