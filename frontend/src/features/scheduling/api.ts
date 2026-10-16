import { z } from "zod";

import { apiGet, apiPost } from "@/lib/api-client";

import {
  appointmentSchema,
  branchSchema,
  clinicianSchema,
  dayEntrySchema,
  followUpDueSchema,
  hoursSchema,
  queueEntrySchema,
  slotSchema,
  triageSchema,
  type Appointment,
  type Branch,
  type Clinician,
  type DayEntry,
  type FollowUpDue,
  type Hours,
  type QueueEntry,
  type Slot,
  type Triage,
} from "./schemas";

const q = encodeURIComponent;

export function getBranches(): Promise<Branch[]> {
  return apiGet("/tenancy/branches", z.array(branchSchema));
}

export function getClinicians(): Promise<Clinician[]> {
  return apiGet("/staff/clinicians", z.array(clinicianSchema));
}

/** Who is with a clinician and who is waiting. Each look is one diary line. */
export function getQueue(branchId: string): Promise<QueueEntry[]> {
  return apiGet(`/appointments/queue?branch_id=${q(branchId)}`, z.array(queueEntrySchema));
}

/** Every visit at a branch on one Lagos day ("YYYY-MM-DD"). Each look is one diary line. */
export function getDayList(branchId: string, day: string): Promise<DayEntry[]> {
  return apiGet(
    `/appointments/day?branch_id=${q(branchId)}&date=${q(day)}`,
    z.array(dayEntrySchema),
  );
}

export function registerWalkIn(form: {
  patient_id: string;
  branch_id: string;
  clinician_id: string | null;
}): Promise<Appointment> {
  return apiPost("/appointments/walk-ins", form, appointmentSchema);
}

export function bookVisit(form: {
  patient_id: string;
  branch_id: string;
  clinician_id: string;
  starts_at: string; // with a time zone, for example 2026-11-02T09:00:00+01:00
  visit_type?: "in_person" | "teleconsult";
  duration_minutes?: number; // a chosen free slot books exactly its length
}): Promise<Appointment> {
  return apiPost("/appointments", form, appointmentSchema);
}

export type VisitAction = "check-in" | "cancel" | "no-show";

/** Check in, cancel or mark a no-show. The backend decides whether the move is allowed. */
export function changeVisit(appointmentId: string, action: VisitAction): Promise<Appointment> {
  return apiPost(`/appointments/${q(appointmentId)}/${action}`, {}, appointmentSchema);
}

/**
 * Doctors and nurses: how urgent a patient who is here is. Sent directly (the queue
 * needs the network anyway); the device-made ID makes a double tap harmless.
 */
export function recordTriage(
  appointmentId: string,
  level: string,
  redFlags: string[],
): Promise<Triage> {
  return apiPost(
    `/appointments/${q(appointmentId)}/triage`,
    { id: crypto.randomUUID(), level, red_flags: redFlags },
    triageSchema,
  );
}

// Clinicians' weekly hours and free slots (no patient data)

export type HoursForm = {
  branch_id: string;
  weekday: number;
  starts: string; // "09:00", Lagos time
  ends: string;
  visit_type: "in_person" | "teleconsult";
  slot_minutes: number;
};

export function getHours(clinicianId: string): Promise<Hours[]> {
  return apiGet(`/availability?clinician_id=${q(clinicianId)}`, z.array(hoursSchema));
}

/** Publish weekly hours for yourself. */
export function publishHours(form: HoursForm): Promise<Hours> {
  return apiPost("/availability", { id: crypto.randomUUID(), ...form }, hoursSchema);
}

export function removeHours(hoursId: string): Promise<Hours> {
  return apiPost(`/availability/${q(hoursId)}/remove`, {}, hoursSchema);
}

/** Free slots of one clinician and visit type, from a Lagos day ("2026-11-02"). */
export function getFreeSlots(
  clinicianId: string,
  visitType: "in_person" | "teleconsult",
  fromDay: string,
  days = 7,
): Promise<Slot[]> {
  const query = new URLSearchParams({
    clinician_id: clinicianId,
    visit_type: visitType,
    from_day: fromDay,
    days: String(days),
  });
  return apiGet(`/availability/slots?${query}`, z.array(slotSchema));
}

// Follow-ups due (FR-C5): front desk books them, then marks them booked or cancelled.

export function getFollowUpsDue(until: string): Promise<FollowUpDue[]> {
  return apiGet(`/follow-ups/due?until=${q(until)}`, z.array(followUpDueSchema));
}

export function markFollowUpBooked(followUpId: string): Promise<FollowUpDue> {
  return apiPost(`/follow-ups/${q(followUpId)}/booked`, {}, followUpDueSchema);
}

export function cancelFollowUp(followUpId: string): Promise<FollowUpDue> {
  return apiPost(`/follow-ups/${q(followUpId)}/cancel`, {}, followUpDueSchema);
}
