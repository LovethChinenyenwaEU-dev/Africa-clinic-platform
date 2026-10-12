import type { ZodError } from "zod";

export type FieldErrors = { email?: string; password?: string };

/** One friendly message per field, taken from the first problem found in that field. */
export function fieldErrorsFrom(error: ZodError): FieldErrors {
  const errors: FieldErrors = {};
  for (const issue of error.issues) {
    const field = issue.path[0];
    if ((field === "email" || field === "password") && !errors[field]) {
      errors[field] = issue.message;
    }
  }
  return errors;
}