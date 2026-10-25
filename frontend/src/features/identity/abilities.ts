import type { Role } from "./schemas";

/*
 * What each role may DO on a screen, mirroring the backend's capabilities
 * (backend/app/modules/identity/permissions.py). It only decides which buttons
 * to show: the backend still checks every request and has the final word.
 */

export type Ability =
  | "register_patient"
  | "manage_consent"
  | "manage_appointments"
  | "run_consultation"
  | "prescribe"
  | "set_prices"
  | "take_payments";

const FRONT_LINE: readonly Role[] = ["front_desk", "nurse", "doctor"];
const CLINICIANS: readonly Role[] = ["nurse", "doctor"];

const ABILITIES: Record<Ability, readonly Role[]> = {
  register_patient: FRONT_LINE, // patient:write
  manage_consent: FRONT_LINE, // consent:read and consent:write
  manage_appointments: FRONT_LINE, // appointment:read and appointment:write
  run_consultation: CLINICIANS, // appointment:consult, clinical:read and clinical:write
  prescribe: ["doctor"], // clinical:prescribe
  set_prices: ["admin"], // price:write
  take_payments: ["front_desk", "billing"], // invoice:write, payment:record, refund:request
};

export function can(role: Role, ability: Ability): boolean {
  return ABILITIES[ability].includes(role);
}
