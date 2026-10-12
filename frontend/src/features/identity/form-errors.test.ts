import { describe, expect, it } from "vitest";

import { fieldErrorsFrom } from "./form-errors";
import { ROLE_LABELS } from "./roles";
import { loginFormSchema, roleSchema } from "./schemas";

function errorsFor(input: unknown) {
  const result = loginFormSchema.safeParse(input);
  return result.success ? null : fieldErrorsFrom(result.error);
}

describe("fieldErrorsFrom", () => {
  it("gives one friendly message per empty field", () => {
    expect(errorsFor({ email: "", password: "" })).toEqual({
      email: "Enter your email.",
      password: "Enter your password.",
    });
  });

  it("treats an email of only spaces as empty", () => {
    expect(errorsFor({ email: "   ", password: "a-long-enough-password" })).toEqual({
      email: "Enter your email.",
    });
  });

  it("reports only the field that is wrong", () => {
    expect(errorsFor({ email: "a@example.com", password: "x".repeat(129) })).toEqual({
      password: "That password is too long.",
    });
  });

  it("finds nothing wrong with a normal form", () => {
    expect(errorsFor({ email: "a@example.com", password: "a-long-enough-password" })).toBeNull();
  });
});

describe("ROLE_LABELS", () => {
  it("has a label for every role the schema knows", () => {
    expect(Object.keys(ROLE_LABELS).sort()).toEqual([...roleSchema.options].sort());
  });
});