import type { Role } from "./schemas";

/*
 * The one table that says which screens each role can open. The menu is built
 * from it, and every page checks it on the server too: hiding a link is a
 * convenience, the page check (and the backend) are the real protection.
 * It mirrors the backend's permissions; the backend stays the final word.
 */

export type ScreenKey = "home" | "patients" | "queue" | "audit";

type Screen = { href: string; label: string; roles: readonly Role[] };

const EVERYONE: readonly Role[] = ["admin", "front_desk", "nurse", "doctor", "billing"];

export const SCREENS: Record<ScreenKey, Screen> = {
  home: { href: "/", label: "Home", roles: EVERYONE },
  // Admins supervise through the diary and have no patient access (ADR-0003).
  patients: { href: "/patients", label: "Patients", roles: ["front_desk", "nurse", "doctor", "billing"] },
  queue: { href: "/queue", label: "Today's queue", roles: ["front_desk", "nurse", "doctor"] },
  audit: { href: "/audit", label: "Audit log", roles: ["admin"] },
};

export type NavItem = { href: string; label: string };

export function canOpen(role: Role, screen: ScreenKey): boolean {
  return SCREENS[screen].roles.includes(role);
}

/** The menu for one role, in a fixed order. */
export function navFor(role: Role): NavItem[] {
  return (Object.keys(SCREENS) as ScreenKey[])
    .filter((key) => canOpen(role, key))
    .map((key) => ({ href: SCREENS[key].href, label: SCREENS[key].label }));
}
