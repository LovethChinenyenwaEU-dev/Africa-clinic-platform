import { describe, expect, it } from "vitest";

import { can } from "./abilities";

describe("can", () => {
  it.each(["front_desk", "nurse", "doctor"] as const)("lets %s register and manage consent", (role) => {
    expect(can(role, "register_patient")).toBe(true);
    expect(can(role, "manage_consent")).toBe(true);
    expect(can(role, "manage_appointments")).toBe(true);
  });

  it.each(["admin", "billing"] as const)("keeps %s away from both", (role) => {
    expect(can(role, "register_patient")).toBe(false);
    expect(can(role, "manage_consent")).toBe(false);
    expect(can(role, "manage_appointments")).toBe(false);
  });
});

describe("run_consultation", () => {
  it("is for doctors and nurses only", () => {
    expect(can("doctor", "run_consultation")).toBe(true);
    expect(can("nurse", "run_consultation")).toBe(true);
    for (const role of ["front_desk", "admin", "billing"] as const) {
      expect(can(role, "run_consultation")).toBe(false);
    }
  });
});
