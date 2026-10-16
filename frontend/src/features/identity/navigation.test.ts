import { describe, expect, it } from "vitest";

import { canOpen, navFor } from "./navigation";

const labels = (role: Parameters<typeof navFor>[0]) => navFor(role).map((item) => item.label);

describe("navFor", () => {
  it("gives front desk patients and the queue", () => {
    expect(labels("front_desk")).toEqual(["Home", "Patients", "Today's queue"]);
  });

  it("gives nurses and doctors their own weekly hours too", () => {
    for (const role of ["nurse", "doctor"] as const) {
      expect(labels(role)).toEqual(["Home", "Patients", "Today's queue", "My hours"]);
    }
    for (const role of ["front_desk", "admin", "billing"] as const) {
      expect(canOpen(role, "availability")).toBe(false);
    }
  });

  it("gives admins the audit log and no patient screens", () => {
    expect(labels("admin")).toEqual(["Home", "Audit log"]);
    expect(canOpen("admin", "patients")).toBe(false);
  });

  it("gives billing patients only, for now", () => {
    expect(labels("billing")).toEqual(["Home", "Patients"]);
  });

  it("never offers the audit log to anyone but admins", () => {
    for (const role of ["front_desk", "nurse", "doctor", "billing"] as const) {
      expect(canOpen(role, "audit")).toBe(false);
    }
  });
});

describe("the encounter screen", () => {
  it("opens for doctors and nurses only, and is never in the menu", () => {
    expect(canOpen("doctor", "encounter")).toBe(true);
    expect(canOpen("nurse", "encounter")).toBe(true);
    for (const role of ["front_desk", "admin", "billing"] as const) {
      expect(canOpen(role, "encounter")).toBe(false);
    }
    expect(labels("doctor")).not.toContain("Encounter");
  });
});
