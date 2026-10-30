import { describe, expect, it } from "vitest";

import { canOpen, currentHref, navFor } from "./navigation";

const labels = (role: Parameters<typeof navFor>[0]) => navFor(role).map((item) => item.label);

describe("navFor", () => {
  it("gives front desk patients, the queue and billing", () => {
    expect(labels("front_desk")).toEqual([
      "Home",
      "Patients",
      "Today's queue",
      "Billing",
      "Prices",
    ]);
  });

  it("gives nurses and doctors their own weekly hours too", () => {
    for (const role of ["nurse", "doctor"] as const) {
      expect(labels(role)).toEqual(["Home", "Patients", "Today's queue", "My hours"]);
    }
    for (const role of ["front_desk", "admin", "billing"] as const) {
      expect(canOpen(role, "availability")).toBe(false);
    }
  });

  it("gives admins the audit log, prices, refunds and takings, and no patient screens", () => {
    expect(labels("admin")).toEqual(["Home", "Audit log", "Prices", "Refunds", "Takings"]);
    expect(canOpen("admin", "billing")).toBe(false); // finding a patient needs patient access
    expect(canOpen("admin", "invoice")).toBe(true); // to decide refunds
    expect(canOpen("admin", "patients")).toBe(false);
  });

  it("gives billing patients, billing, prices and the takings", () => {
    expect(labels("billing")).toEqual(["Home", "Patients", "Billing", "Prices", "Takings"]);
  });

  it("lets only admins decide refunds, and keeps the takings from the front desk", () => {
    for (const role of ["front_desk", "billing"] as const) {
      expect(canOpen(role, "refunds")).toBe(false);
    }
    expect(canOpen("front_desk", "takings")).toBe(false);
  });

  it("keeps nurses and doctors away from money", () => {
    for (const role of ["nurse", "doctor"] as const) {
      for (const screen of ["billing", "prices", "invoice", "refunds", "takings"] as const) {
        expect(canOpen(role, screen)).toBe(false);
      }
    }
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

describe("my devices", () => {
  it("opens for every role, and sits in the top bar, not the menu", () => {
    for (const role of ["admin", "front_desk", "nurse", "doctor", "billing"] as const) {
      expect(canOpen(role, "account")).toBe(true);
      expect(labels(role)).not.toContain("My devices");
    }
  });
});

describe("currentHref", () => {
  const items = navFor("billing");

  it("marks only the closest menu item", () => {
    expect(currentHref("/billing/prices", items)).toBe("/billing/prices");
    expect(currentHref("/billing", items)).toBe("/billing");
    expect(currentHref("/billing/invoices/abc", items)).toBe("/billing");
    expect(currentHref("/", items)).toBe("/");
    expect(currentHref("/billingx", items)).toBeNull();
  });
});
