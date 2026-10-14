import { z } from "zod";

import { todayInLagos } from "@/lib/format";

export const SEXES = ["female", "male", "other"] as const;

// What the backend answers for a patient. No clinic or staff IDs ever come back.
export const patientSchema = z.object({
  id: z.string().uuid(),
  full_name: z.string(),
  date_of_birth: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  sex: z.string(),
  phone: z.string().nullable(),
});
export type Patient = z.infer<typeof patientSchema>;

export const patientListSchema = z.array(patientSchema);

// The registration form. Friendly messages only: the backend remains the real check.
export const registerFormSchema = z.object({
  full_name: z
    .string()
    .trim()
    .min(1, "Enter the patient's full name.")
    .max(200, "That name is too long."),
  date_of_birth: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Enter the date of birth.")
    .refine((value) => value >= "1900-01-01", "That date of birth is too early.")
    .refine((value) => value <= todayInLagos(), "The date of birth cannot be in the future."),
  sex: z.enum(SEXES, { message: "Choose the patient's sex." }),
  phone: z
    .string()
    .trim()
    .max(40, "That phone number is too long.")
    .transform((value) => (value === "" ? null : value)),
});
export type RegisterForm = z.input<typeof registerFormSchema>;
export type RegisterPayload = z.output<typeof registerFormSchema>;

// The backend's possible-duplicate warning (409): IDs and reasons only, never names.
export const DUPLICATE_REASONS = ["same_phone", "same_name_and_birth_date"] as const;
export const duplicateWarningSchema = z.object({
  message: z.string(),
  matches: z
    .array(z.object({ patient_id: z.string().uuid(), reason: z.enum(DUPLICATE_REASONS) }))
    .min(1),
});
export type DuplicateMatch = z.infer<typeof duplicateWarningSchema>["matches"][number];
