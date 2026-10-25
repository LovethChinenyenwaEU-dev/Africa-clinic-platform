/*
 * Money on the screens. The server counts in whole kobo (100 kobo = 1 naira); people
 * type and read naira. Typed amounts are turned into kobo by reading the text, never
 * with floating point, so "0.29" is 29 kobo and not 28.999999.
 */

/** 500000 -> "₦5,000.00"; -150 -> "-₦1.50". Built by hand: the same on every device. */
export function formatNaira(kobo: number): string {
  const sign = kobo < 0 ? "-" : "";
  const abs = Math.abs(kobo);
  const whole = String(Math.trunc(abs / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const part = String(abs % 100).padStart(2, "0");
  return `${sign}₦${whole}.${part}`;
}

// "5000", "5,000", "5000.5", "5,000.50", "₦5,000" and " 5 000 " are all fine.
const AMOUNT = /^(\d{1,3}(?:[, ]\d{3})*|\d+)(?:\.(\d{1,2}))?$/;

/** What a person typed, in naira, as whole kobo; null when it is not a plain amount. */
export function parseNaira(text: string): number | null {
  const cleaned = text.trim().replace(/^₦\s*/, "").replace(/^NGN\s*/i, "");
  const match = AMOUNT.exec(cleaned);
  if (!match) return null;
  const whole = Number(match[1].replace(/[, ]/g, ""));
  const fraction = (match[2] ?? "").padEnd(2, "0");
  const kobo = whole * 100 + Number(fraction || "0");
  return Number.isSafeInteger(kobo) ? kobo : null;
}

/** Kobo shown in a text box for editing: 500000 -> "5000.00". */
export function nairaInput(kobo: number): string {
  return `${Math.trunc(kobo / 100)}.${String(kobo % 100).padStart(2, "0")}`;
}
