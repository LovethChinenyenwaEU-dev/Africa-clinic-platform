import type { Readings } from "./api";
import { READING_LABELS } from "./labels";
import { READING_FIELDS, type ReadingField, type Vitals } from "./schemas";

// These are measured in whole numbers; the rest keep their decimals as exact text.
const WHOLE: ReadonlySet<ReadingField> = new Set([
  "systolic_mmhg",
  "diastolic_mmhg",
  "pulse_bpm",
  "respiratory_rate",
  "spo2_pct",
]);

export type ReadingsForm = Record<ReadingField, string>;

export const EMPTY_READINGS: ReadingsForm = Object.fromEntries(
  READING_FIELDS.map((field) => [field, ""]),
) as ReadingsForm;

/**
 * Turn the boxes into readings to send. Empty boxes are left out. Something that
 * is not a number gets a message; the real range checks stay in the backend.
 */
export function readingsFromForm(
  form: ReadingsForm,
): { readings: Readings } | { problem: string } {
  const readings: Readings = {};
  for (const field of READING_FIELDS) {
    const text = form[field].trim().replace(",", ".");
    if (text === "") continue;
    const pattern = WHOLE.has(field) ? /^\d+$/ : /^\d+(\.\d+)?$/;
    if (!pattern.test(text)) {
      const { label } = READING_LABELS[field];
      return { problem: `${label} must be ${WHOLE.has(field) ? "a whole number" : "a number"}.` };
    }
    readings[field] = WHOLE.has(field) ? Number(text) : text;
  }
  if (Object.keys(readings).length === 0) {
    return { problem: "Enter at least one reading." };
  }
  return { readings };
}

/** A filled-in form from an existing set, for correcting it. */
export function formFromVitals(vitals: Vitals): ReadingsForm {
  return Object.fromEntries(
    READING_FIELDS.map((field) => [field, vitals[field] === null ? "" : String(vitals[field])]),
  ) as ReadingsForm;
}

/** "BP 120/80 mmHg · Pulse 88 /min · Temperature 37.5 °C" */
export function describeVitals(vitals: Vitals): string {
  const parts: string[] = [];
  if (vitals.systolic_mmhg !== null && vitals.diastolic_mmhg !== null) {
    parts.push(`BP ${vitals.systolic_mmhg}/${vitals.diastolic_mmhg} mmHg`);
  }
  for (const field of READING_FIELDS) {
    if (field === "systolic_mmhg" || field === "diastolic_mmhg") continue;
    const value = vitals[field];
    if (value !== null) {
      const { label, unit } = READING_LABELS[field];
      parts.push(`${label} ${value} ${unit}`);
    }
  }
  return parts.join(" · ");
}
