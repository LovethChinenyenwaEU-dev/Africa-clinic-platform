import { z } from "zod";

import { apiGet } from "@/lib/api-client";

import { auditEventSchema, staffSchema, type AuditEvent, type StaffMember } from "./schemas";

// The backend's largest page.
export const MAX_EVENTS = 200;

export type AuditFilters = {
  patientId: string; // empty for everyone
  staffId: string; // empty for everyone
  fromDay: string; // "YYYY-MM-DD" in Lagos, empty for no start
  toDay: string; // "YYYY-MM-DD" in Lagos, inclusive, empty for no end
};

export const NO_FILTERS: AuditFilters = { patientId: "", staffId: "", fromDay: "", toDay: "" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DAY = /^\d{4}-\d{2}-\d{2}$/;

function nextDay(day: string): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date + 1)).toISOString().slice(0, 10);
}

/**
 * The query string for the backend. Days are whole Lagos days: "from 3 Nov to 3 Nov"
 * means 3 Nov 00:00 up to (not including) 4 Nov 00:00, Lagos time.
 * Returns a problem instead when a filter makes no sense, so nothing is sent.
 */
export function auditQuery(filters: AuditFilters): { query: string } | { problem: string } {
  const params = new URLSearchParams({ limit: String(MAX_EVENTS) });
  const patientId = filters.patientId.trim();
  if (patientId) {
    if (!UUID.test(patientId)) {
      return { problem: "A patient ID looks like 8-4-4-4-12 letters and numbers." };
    }
    params.set("patient_id", patientId);
  }
  if (filters.staffId) params.set("staff_id", filters.staffId);
  if (filters.fromDay) {
    if (!DAY.test(filters.fromDay)) return { problem: "Choose a valid start day." };
    params.set("since", `${filters.fromDay}T00:00:00+01:00`);
  }
  if (filters.toDay) {
    if (!DAY.test(filters.toDay)) return { problem: "Choose a valid end day." };
    params.set("until", `${nextDay(filters.toDay)}T00:00:00+01:00`);
  }
  if (filters.fromDay && filters.toDay && filters.fromDay > filters.toDay) {
    return { problem: "The start day must not be after the end day." };
  }
  return { query: params.toString() };
}

/** The clinic's diary, newest first. Reading it is itself written in the diary. */
export function getAuditEvents(query: string): Promise<AuditEvent[]> {
  return apiGet(`/audit/events?${query}`, z.array(auditEventSchema));
}

/** The clinic's staff, so diary lines can show names instead of IDs. Admins only. */
export function getStaff(): Promise<StaffMember[]> {
  return apiGet("/staff", z.array(staffSchema));
}
