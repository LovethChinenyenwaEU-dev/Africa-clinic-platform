import type { DashboardDay } from "./schemas";

/*
 * Small helpers for the dashboard screen, kept apart so they can be tested without a page.
 */

export const MAX_DAYS = 92; // the backend's limit

export type Preset = 7 | 30 | 90;
export const PRESETS: Preset[] = [7, 30, 90];

/** "YYYY-MM-DD" plus or minus whole days (calendar days, no time zone involved). */
export function addDays(day: string, days: number): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date + days)).toISOString().slice(0, 10);
}

/** The last N days up to and including today. */
export function lastDays(days: Preset, today: string): { from: string; to: string } {
  return { from: addDays(today, -(days - 1)), to: today };
}

/** How many days a range covers, both ends included. */
export function daysIn(from: string, to: string): number {
  return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000) + 1;
}

/** A problem with the chosen days, or null when the backend will accept them. */
export function rangeProblem(from: string, to: string): string | null {
  if (!from || !to) return "Choose both days.";
  if (from > to) return "The first day must not come after the last day.";
  if (daysIn(from, to) > MAX_DAYS) return `Choose at most ${MAX_DAYS} days.`;
  return null;
}

/** 0.253 -> "25%". Nothing to measure -> an em dash, never "0%". */
export function percent(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

/** 42.5 -> "43 min"; 135 -> "2 h 15 min". */
export function minutes(value: number | null): string {
  if (value === null) return "—";
  const whole = Math.round(value);
  if (whole < 60) return `${whole} min`;
  const rest = whole % 60;
  return rest ? `${Math.floor(whole / 60)} h ${rest} min` : `${whole / 60} h`;
}

/** Bar heights as a share (0 to 1) of the busiest day. All zero when nothing happened. */
export function barShares(days: DashboardDay[]): number[] {
  const most = Math.max(0, ...days.map((day) => day.visits));
  return days.map((day) => (most ? day.visits / most : 0));
}

/** "Mon 3 Nov": short enough to sit under a bar. */
export function shortDay(day: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${day}T00:00:00Z`));
}
