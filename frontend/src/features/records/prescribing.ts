import type { PrescriptionDetails } from "./api";
import { ROUTE_LABELS } from "./labels";

export type PrescriptionForm = Record<keyof PrescriptionDetails, string>;

export const EMPTY_PRESCRIPTION: PrescriptionForm = {
  medicine: "",
  strength: "",
  dose: "",
  route: "oral",
  frequency: "",
  duration: "",
  instructions: "",
};

const REQUIRED: Array<[keyof PrescriptionForm, string]> = [
  ["medicine", "Enter the medicine."],
  ["dose", "Enter the dose, for example 2 tablets."],
  ["frequency", "Enter how often, for example twice daily."],
  ["duration", "Enter for how long, for example 5 days."],
];

/** The form, checked and tidied, or the first thing missing. The server checks again. */
export function prescriptionFromForm(
  form: PrescriptionForm,
): PrescriptionDetails | { problem: string } {
  for (const [field, problem] of REQUIRED) {
    if (!form[field].trim()) return { problem };
  }
  const optional = (value: string) => value.trim() || null;
  return {
    medicine: form.medicine.trim(),
    strength: optional(form.strength),
    dose: form.dose.trim(),
    route: form.route,
    frequency: form.frequency.trim(),
    duration: form.duration.trim(),
    instructions: optional(form.instructions),
  };
}

/** One line a pharmacist can read: "Paracetamol 500 mg, 2 tablets by mouth, 8-hourly for 3 days". */
export function describePrescription(row: PrescriptionDetails): string {
  const name = row.strength ? `${row.medicine} ${row.strength}` : row.medicine;
  const route = (ROUTE_LABELS[row.route] ?? row.route).toLowerCase();
  return `${name}, ${row.dose} ${route}, ${row.frequency} for ${row.duration}`;
}
