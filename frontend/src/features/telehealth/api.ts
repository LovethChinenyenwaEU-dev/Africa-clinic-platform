import { z } from "zod";

import { apiGet, apiPost } from "@/lib/api-client";

import {
  intakeResultSchema,
  messageSchema,
  roomSchema,
  teleconsultStatusSchema,
  type ConsultMode,
  type IntakeResult,
  type Message,
  type Room,
  type TeleconsultStatus,
} from "./schemas";

const q = encodeURIComponent;

export function getTeleconsultStatus(appointmentId: string): Promise<TeleconsultStatus> {
  return apiGet(`/teleconsults/${q(appointmentId)}/status`, teleconsultStatusSchema);
}

/**
 * The reason and the danger-sign screen before a remote visit. No danger sign: the
 * patient joins the remote waiting room. A danger sign: in-person care is advised.
 * Sent directly: the answer decides what staff tell the patient now.
 */
export function submitIntake(
  appointmentId: string,
  reason: string,
  redFlags: string[],
): Promise<IntakeResult> {
  return apiPost(
    `/teleconsults/${q(appointmentId)}/intake`,
    { id: crypto.randomUUID(), reason, red_flags: redFlags },
    intakeResultSchema,
  );
}

// The consult room (the clinician running the remote visit)

export function openRoom(appointmentId: string): Promise<Room> {
  return apiPost(`/teleconsults/${q(appointmentId)}/room`, {}, roomSchema);
}

export type ModeReason = "poor_connection" | "patient_choice" | "clinician_choice";

export function switchMode(
  appointmentId: string,
  mode: ConsultMode,
  reason: ModeReason,
): Promise<Room> {
  return apiPost(`/teleconsults/${q(appointmentId)}/mode`, { mode, reason }, roomSchema);
}

/** The chat. With `since`, only messages sent at or after it: small, for weak networks. */
export function getMessages(appointmentId: string, since?: string): Promise<Message[]> {
  const query = since ? `?since=${q(since)}` : "";
  return apiGet(`/teleconsults/${q(appointmentId)}/messages${query}`, z.array(messageSchema));
}

export function sendMessage(appointmentId: string, body: string): Promise<Message> {
  return apiPost(
    `/teleconsults/${q(appointmentId)}/messages`,
    { id: crypto.randomUUID(), body },
    messageSchema,
  );
}

/** New messages added to what the screen has, once each, oldest first. */
export function mergeMessages<T extends { id: string; sent_at: string }>(
  known: T[],
  fresh: T[],
): T[] {
  const byId = new Map(known.map((message) => [message.id, message]));
  for (const message of fresh) byId.set(message.id, message);
  return [...byId.values()].sort(
    (a, b) => a.sent_at.localeCompare(b.sent_at) || a.id.localeCompare(b.id),
  );
}
