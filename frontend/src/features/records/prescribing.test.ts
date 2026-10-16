import { describe, expect, it } from "vitest";

import { can } from "@/features/identity/abilities";

import { prescriptionRevisionWrite, prescriptionWrite } from "./api";
import { EMPTY_PRESCRIPTION, describePrescription, prescriptionFromForm } from "./prescribing";
import type { Prescription } from "./schemas";

const ENCOUNTER = "33333333-3333-4333-8333-333333333333";
const FILLED = {
  ...EMPTY_PRESCRIPTION,
  medicine: "  Paracetamol ",
  strength: "500 mg",
  dose: "2 tablets",
  frequency: "8-hourly",
  duration: "3 days",
};
const SAVED: Prescription = {
  id: "44444444-4444-4444-8444-444444444444",
  encounter_id: ENCOUNTER,
  patient_id: "11111111-1111-4111-8111-111111111111",
  version_status: "current",
  replaces_id: null,
  medicine: "Paracetamol",
  strength: "500 mg",
  dose: "2 tablets",
  route: "oral",
  frequency: "8-hourly",
  duration: "3 days",
  instructions: null,
  clinical_status: "active",
  recorded_by_id: "55555555-5555-4555-8555-555555555555",
  recorded_at: "2026-10-16T09:00:00Z",
  written_at: "2026-10-16T09:00:00Z",
  synced_late: false,
};

describe("prescriptionFromForm", () => {
  it("tidies the form and leaves empty optional boxes out", () => {
    expect(prescriptionFromForm(FILLED)).toEqual({
      medicine: "Paracetamol",
      strength: "500 mg",
      dose: "2 tablets",
      route: "oral",
      frequency: "8-hourly",
      duration: "3 days",
      instructions: null,
    });
  });

  it.each([
    ["medicine", "Enter the medicine."],
    ["dose", "Enter the dose"],
    ["frequency", "Enter how often"],
    ["duration", "Enter for how long"],
  ] as const)("asks for the %s", (field, problem) => {
    const result = prescriptionFromForm({ ...FILLED, [field]: "  " });

    expect("problem" in result && result.problem).toContain(problem);
  });
});

describe("describePrescription", () => {
  it("reads as one line", () => {
    expect(describePrescription(SAVED)).toBe(
      "Paracetamol 500 mg, 2 tablets by mouth, 8-hourly for 3 days",
    );
  });
});

describe("prescription writes", () => {
  it("queues a new prescription with its own ID and the device time", () => {
    const written = prescriptionWrite(ENCOUNTER, SAVED, new Date("2026-10-16T09:30:00Z"));

    expect(written).toMatchObject({
      path: `/encounters/${ENCOUNTER}/prescriptions`,
      body: { medicine: "Paracetamol", written_at: "2026-10-16T09:30:00.000Z" },
      label: "Prescription",
      encounterId: ENCOUNTER,
    });
    expect((written.body as { id: string }).id).toMatch(/^[0-9a-f-]{36}$/);
    expect((written.body as { id: string }).id).not.toBe(SAVED.id); // always a fresh ID
  });

  it("stops a prescription by sending it whole with the new status", () => {
    const stop = prescriptionRevisionWrite(SAVED, "stopped");

    expect(stop.path).toBe(`/prescriptions/${SAVED.id}/revisions`);
    expect(stop.body).toMatchObject({ medicine: "Paracetamol", clinical_status: "stopped" });
    expect(stop.label).toBe("Prescription change"); // never the medicine's name
  });
});

describe("who prescribes", () => {
  it("is doctors only, like the backend", () => {
    expect(can("doctor", "prescribe")).toBe(true);
    for (const role of ["nurse", "front_desk", "admin", "billing"] as const) {
      expect(can(role, "prescribe")).toBe(false);
    }
  });
});
