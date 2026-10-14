import type { Role } from "./schemas";

/*
 * What each role may DO on a screen, mirroring the backend's capabilities
 * (backend/app/modules/identity/permissions.py). It only decides which buttons
 * to show: the backend still checks every request and has the final word.
 */

export type Ability = "register_patient" | "manage_consent";

const FRONT_LINE: readonly Role[] = ["front_desk", "nurse", "doctor"];

const ABILITIES: Record<Ability, readonly Role[]> = {
  register_patient: FRONT_LINE, // patient:write
  manage_consent: FRONT_LINE, // consent:read and consent:write
};

export function can(role: Role, ability: Ability): boolean {
  return ABILITIES[ability].includes(role);
}
