import type { Role } from "./schemas";

/*
 * The one table that says which screens each role can open. The menu is built
 * from it, and every page checks it on the server too: hiding a link is a
 * convenience, the page check (and the backend) are the real protection.
 * It mirrors the backend's permissions; the backend stays the final word.
 */

export type ScreenKey =
  | "home"
  | "patients"
  | "queue"
  | "availability"
  | "encounter"
  | "audit"
  | "billing"
  | "prices"
  | "invoice";

// inMenu: false for screens reached from another screen (an encounter opens from the queue).
type Screen = { href: string; label: string; roles: readonly Role[]; inMenu: boolean };

const EVERYONE: readonly Role[] = ["admin", "front_desk", "nurse", "doctor", "billing"];

export const SCREENS: Record<ScreenKey, Screen> = {
  home: { href: "/", label: "Home", roles: EVERYONE, inMenu: true },
  // Admins supervise through the diary and have no patient access (ADR-0003).
  patients: {
    href: "/patients",
    label: "Patients",
    roles: ["front_desk", "nurse", "doctor", "billing"],
    inMenu: true,
  },
  queue: {
    href: "/queue",
    label: "Today's queue",
    roles: ["front_desk", "nurse", "doctor"],
    inMenu: true,
  },
  // A clinician's own weekly hours, in person and remote (FR-C1).
  availability: { href: "/availability", label: "My hours", roles: ["nurse", "doctor"], inMenu: true },
  // The clinical record: doctors and nurses only, like the backend's clinical:read.
  encounter: { href: "/encounters", label: "Encounter", roles: ["nurse", "doctor"], inMenu: false },
  audit: { href: "/audit", label: "Audit log", roles: ["admin"], inMenu: true },
  // Billing (Week 10): front desk and billing find a patient's visits and bill them.
  billing: { href: "/billing", label: "Billing", roles: ["front_desk", "billing"], inMenu: true },
  // Everyone who bills reads the price list; only admins change it (price:write).
  prices: {
    href: "/billing/prices",
    label: "Prices",
    roles: ["admin", "front_desk", "billing"],
    inMenu: true,
  },
  // One invoice and its payments. Admins read invoices too, to decide refunds.
  invoice: {
    href: "/billing/invoices",
    label: "Invoice",
    roles: ["admin", "front_desk", "billing"],
    inMenu: false,
  },
};

export type NavItem = { href: string; label: string };

export function canOpen(role: Role, screen: ScreenKey): boolean {
  return SCREENS[screen].roles.includes(role);
}

/** The menu for one role, in a fixed order. */
export function navFor(role: Role): NavItem[] {
  return (Object.keys(SCREENS) as ScreenKey[])
    .filter((key) => SCREENS[key].inMenu && canOpen(role, key))
    .map((key) => ({ href: SCREENS[key].href, label: SCREENS[key].label }));
}

function matches(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** The one menu item for this page: the longest match, so /billing/prices is "Prices",
 * not "Billing" too. */
export function currentHref(pathname: string, items: NavItem[]): string | null {
  const found = items.filter((item) => matches(pathname, item.href));
  found.sort((a, b) => b.href.length - a.href.length);
  return found[0]?.href ?? null;
}
