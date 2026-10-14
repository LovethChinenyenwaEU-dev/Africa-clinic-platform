import type { ZodError } from "zod";

/** One friendly message per field, from the first problem found in that field. */
export function errorsByField<Field extends string>(
  error: ZodError,
  fields: readonly Field[],
): Partial<Record<Field, string>> {
  const errors: Partial<Record<Field, string>> = {};
  for (const issue of error.issues) {
    const field = issue.path[0];
    if (typeof field === "string" && (fields as readonly string[]).includes(field)) {
      const key = field as Field;
      errors[key] ??= issue.message;
    }
  }
  return errors;
}
