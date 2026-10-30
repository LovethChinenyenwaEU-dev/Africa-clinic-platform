import { z } from "zod";

import { apiGet, apiPost } from "@/lib/api-client";

/*
 * Where a person is signed in (Week 11). Each sign-in is one device; ending one signs
 * that device out at once and leaves the others working. The backend checks that a
 * person only ends their own (an admin may end anyone's in the clinic).
 */

export const deviceSchema = z.object({
  id: z.string().uuid(),
  label: z.string(),
  created_at: z.string(),
  last_seen_at: z.string(),
  current: z.boolean(),
});
export type Device = z.infer<typeof deviceSchema>;

const signedOutSchema = z.object({ signed_out: z.literal(true) });

export function getMyDevices(): Promise<Device[]> {
  return apiGet("/staff/me/sessions", z.array(deviceSchema));
}

export async function endMyDevice(id: string): Promise<void> {
  await apiPost(`/staff/me/sessions/${encodeURIComponent(id)}/end`, {}, signedOutSchema);
}

/** This device first, then the most recently used. */
export function sortDevices(devices: Device[]): Device[] {
  return [...devices].sort(
    (a, b) => Number(b.current) - Number(a.current) || b.last_seen_at.localeCompare(a.last_seen_at),
  );
}
