import { describe, expect, it } from "vitest";

import { loginFormSchema, meSchema, tokenResponseSchema } from "./schemas";

describe("loginFormSchema", () => {
  it("tidies the email and accepts a normal login", () => {
    const result = loginFormSchema.parse({
      email: "  nurse@example.com ",
      password: "a-long-enough-password",
    });
    expect(result.email).toBe("nurse@example.com");
  });

  it("refuses empty fields", () => {
    expect(loginFormSchema.safeParse({ email: "", password: "" }).success).toBe(false);
  });

  it("refuses a giant password before it is ever sent", () => {
    const giant = { email: "a@example.com", password: "x".repeat(129) };
    expect(loginFormSchema.safeParse(giant).success).toBe(false);
  });
});

describe("tokenResponseSchema", () => {
  it("accepts a bearer token and refuses anything else", () => {
    expect(tokenResponseSchema.safeParse({ access_token: "abc", token_type: "bearer" }).success).toBe(true);
    expect(tokenResponseSchema.safeParse({ access_token: "", token_type: "bearer" }).success).toBe(false);
    expect(tokenResponseSchema.safeParse({ access_token: "abc", token_type: "basic" }).success).toBe(false);
  });
});

describe("meSchema", () => {
  const valid = {
    id: crypto.randomUUID(),
    tenant_id: crypto.randomUUID(),
    email: "nurse@example.com",
    full_name: "Test Nurse",
    role: "nurse",
  };

  it("accepts what the backend sends", () => {
    expect(meSchema.safeParse(valid).success).toBe(true);
  });

  it("refuses a role the screen does not know", () => {
    expect(meSchema.safeParse({ ...valid, role: "wizard" }).success).toBe(false);
  });

  it("refuses an id that is not a real UUID", () => {
    expect(meSchema.safeParse({ ...valid, id: "not-an-id" }).success).toBe(false);
  });
});