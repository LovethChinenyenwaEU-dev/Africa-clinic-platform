import { PURPOSES, type Consent, type Purpose } from "./schemas";

export type ConsentState =
  | { state: "agreed"; consent: Consent }
  | { state: "withdrawn"; consent: Consent }
  | { state: "not_recorded" };

/**
 * Where each purpose stands now, from the full history. The newest record for a
 * purpose decides: agreed if it was never revoked, withdrawn if it was.
 */
export function currentConsent(history: Consent[]): Record<Purpose, ConsentState> {
  const result = Object.fromEntries(
    PURPOSES.map((purpose) => [purpose, { state: "not_recorded" } as ConsentState]),
  ) as Record<Purpose, ConsentState>;

  const newestFirst = [...history].sort((a, b) => b.granted_at.localeCompare(a.granted_at));
  for (const purpose of PURPOSES) {
    const newest = newestFirst.find((consent) => consent.purpose === purpose);
    if (newest) {
      result[purpose] = newest.revoked_at
        ? { state: "withdrawn", consent: newest }
        : { state: "agreed", consent: newest };
    }
  }
  return result;
}
