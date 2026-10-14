/*
 * Dates and times, shown the same way on every screen and every device.
 * Times are shown in Lagos time, whatever the device's own time zone.
 */

const CLINIC_TIME_ZONE = "Africa/Lagos";

const DATE = new Intl.DateTimeFormat("en-NG", { dateStyle: "medium", timeZone: "UTC" });
const DATE_TIME = new Intl.DateTimeFormat("en-NG", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: CLINIC_TIME_ZONE,
});

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

function partsOf(isoDate: string): [number, number, number] {
  const match = ISO_DATE.exec(isoDate);
  if (!match) throw new RangeError(`Not a date: ${isoDate}`);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** "2026-05-17" as "17 May 2026". A date of birth never shifts by a day. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = partsOf(isoDate);
  return DATE.format(new Date(Date.UTC(year, month - 1, day)));
}

/** A moment from the server, as a Lagos date and time. */
export function formatDateTime(isoMoment: string): string {
  return DATE_TIME.format(new Date(isoMoment));
}

/** Today's date in Lagos as "YYYY-MM-DD", for date boxes and "not in the future" checks. */
export function todayInLagos(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: CLINIC_TIME_ZONE }).format(now);
}

/** "34 years", "7 months" or "12 days": what a clinician wants to see at a glance. */
export function ageFrom(isoDate: string, today: string = todayInLagos()): string {
  const [birthYear, birthMonth, birthDay] = partsOf(isoDate);
  const [year, month, day] = partsOf(today);
  let months = (year - birthYear) * 12 + (month - birthMonth);
  if (day < birthDay) months -= 1;
  if (months >= 24) return `${Math.floor(months / 12)} years`;
  if (months >= 1) return `${months} month${months === 1 ? "" : "s"}`;
  const days = Math.round(
    (Date.UTC(year, month - 1, day) - Date.UTC(birthYear, birthMonth - 1, birthDay)) / 86_400_000,
  );
  return `${days} day${days === 1 ? "" : "s"}`;
}
