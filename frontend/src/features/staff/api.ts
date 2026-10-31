import { z } from "zod";

import { deviceSchema, type Device } from "@/features/identity/devices";
import { roleSchema } from "@/features/identity/schemas";
import { apiGet, apiPost } from "@/lib/api-client";

/*
 * The admin's staff screen (Week 11): who works here, switching people off and on, their
 * signed-in devices, and resetting an authenticator app after a lost phone. The backend
 * checks every rule again (admins only, nobody resets their own app, the last admin stays).
 */

export const MIN_PASSWORD_LENGTH = 10; // the backend's rule

export const mfaStatusSchema = z.enum(["set_up", "waiting", "not_needed"]);
export type MfaStatus = z.infer<typeof mfaStatusSchema>;

export const MFA_LABELS: Record<MfaStatus, string> = {
  set_up: "Authenticator app set up",
  waiting: "Sets up the authenticator app at next sign-in",
  not_needed: "Password only (role)",
};

export const staffMemberSchema = z.object({
  id: z.string().uuid(),
  email: z.string(),
  full_name: z.string(),
  role: roleSchema,
  is_active: z.boolean(),
});
export const staffListItemSchema = staffMemberSchema.extend({ mfa: mfaStatusSchema });
export type StaffListItem = z.infer<typeof staffListItemSchema>;

export const newStaffSchema = z.object({
  full_name: z.string().trim().min(1, "Enter their full name.").max(120),
  email: z.string().trim().email("Enter a valid email address."),
  role: roleSchema,
  password: z
    .string()
    .min(MIN_PASSWORD_LENGTH, `At least ${MIN_PASSWORD_LENGTH} characters.`)
    .max(128, "At most 128 characters."),
});
export type NewStaff = z.infer<typeof newStaffSchema>;

const q = encodeURIComponent;
const done = z.object({}).loose(); // {"signed_out": true} or {"reset": true}

export function listStaff(): Promise<StaffListItem[]> {
  return apiGet("/staff", z.array(staffListItemSchema));
}

export function addStaff(person: NewStaff) {
  return apiPost("/staff", person, staffMemberSchema);
}

export function setActive(staffId: string, active: boolean) {
  const action = active ? "activate" : "deactivate";
  return apiPost(`/staff/${q(staffId)}/${action}`, {}, staffMemberSchema);
}

export function staffDevices(staffId: string): Promise<Device[]> {
  return apiGet(`/staff/${q(staffId)}/sessions`, z.array(deviceSchema));
}

export async function endStaffDevice(staffId: string, deviceId: string): Promise<void> {
  await apiPost(`/staff/${q(staffId)}/sessions/${q(deviceId)}/end`, {}, done);
}

export async function resetApp(staffId: string): Promise<void> {
  await apiPost(`/staff/${q(staffId)}/mfa/reset`, {}, done);
}

/** Active people first, then by name. */
export function sortStaff(people: StaffListItem[]): StaffListItem[] {
  return [...people].sort(
    (a, b) => Number(b.is_active) - Number(a.is_active) || a.full_name.localeCompare(b.full_name),
  );
}
