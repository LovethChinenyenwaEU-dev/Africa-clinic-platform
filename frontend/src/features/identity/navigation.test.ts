import { describe, expect, it } from "vitest";

import { canOpen, navFor } from "./navigation";

const labels = (role: Parameters<typeof navFor>[0]) => navFor(role).map((item) => item.label);

describe("navFor", () => {
  it("gives front desk, nurses and doctors patients and the queue", () => {
    for (const role of ["front_desk", "nurse", "doctor"] as const) {
      expect(labels(role)).toEqual(["Home", "Patients", "Today's queue"]);
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
