import { z } from "zod";

import { apiGet, apiPost } from "@/lib/api-client";

import {
  appointmentSchema,
  branchSchema,
  clinicianSchema,
  dayEntrySchema,
  queueEntrySchema,
  type Appointment,
  type Branch,
  type Clinician,
  type DayEntry,
  type QueueEntry,
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
}): Promise<Appointment> {
  return apiPost("/appointments", form, appointmentSchema);
}

export type VisitAction = "check-in" | "cancel" | "no-show";

/** Check in, cancel or mark a no-show. The backend decides whether the move is allowed. */
export function changeVisit(appointmentId: string, action: VisitAction): Promise<Appointment> {
  return apiPost(`/appointments/${q(appointmentId)}/${action}`, {}, appointmentSchema);
}
