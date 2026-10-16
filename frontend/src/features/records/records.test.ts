import { beforeEach, describe, expect, it, vi } from "vitest";

import { addAllergy, recordVitals, signOff, startVisit } from "./api";
import { EMPTY_READINGS, describeVitals, formFromVitals, readingsFromForm } from "./readings";
import { vitalsSchema, type Encounter, type Vitals } from "./schemas";

const fetchMock = vi.fn();
const PATIENT = "11111111-1111-4111-8111-111111111111";
const VISIT = "22222222-2222-4222-8222-222222222222";
const ENCOUNTER: Encounter = {
  id: "33333333-3333-4333-8333-333333333333",
  patient_id: PATIENT,
  appointment_id: VISIT,
  clinician_id: "44444444-4444-4444-8444-444444444444",
  status: "open",
  opened_at: "2026-11-02T08:00:00Z",
  closed_at: null,
  closed_by_id: null,
};
const VITALS: Vitals = {
  id: "55555555-5555-4555-8555-555555555555",
  encounter_id: ENCOUNTER.id,
  patient_id: PATIENT,
  status: "current",
  replaces_id: null,
  systolic_mmhg: 120,
  diastolic_mmhg: 80,
  pulse_bpm: 88,
  respiratory_rate: null,
  spo2_pct: null,
  temperature_c: "37.5",
  weight_kg: null,
  height_cm: null,
  measured_at: "2026-11-02T08:05:00Z",
  recorded_by_id: ENCOUNTER.clinician_id,
  recorded_at: "2026-11-02T08:05:00Z",
  synced_late: false,
};

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("readingsFromForm", () => {
  it("leaves empty boxes out, keeps decimals exact and accepts a comma", () => {
    const result = readingsFromForm({
      ...EMPTY_READINGS,
      pulse_bpm: " 88 ",
      temperature_c: "37,5",
    });

    expect(result).toEqual({ readings: { pulse_bpm: 88, temperature_c: "37.5" } });
  });

  it.each([
    [{ pulse_bpm: "88.5" }, "Pulse must be a whole number."],
    [{ temperature_c: "hot" }, "Temperature must be a number."],
    [{}, "Enter at least one reading."],
  ])("explains %j", (change, problem) => {
    expect(readingsFromForm({ ...EMPTY_READINGS, ...change })).toEqual({ problem });
  });

  it("refills the form from a saved set, for a correction", () => {
    expect(formFromVitals(VITALS)).toMatchObject({ systolic_mmhg: "120", temperature_c: "37.5" });
  });

  it("describes a set in one line", () => {
    expect(describeVitals(VITALS)).toBe("BP 120/80 mmHg · Pulse 88 /min · Temperature 37.5 °C");
  });
});

describe("synced late", () => {
  it("reads the late mark, and treats an answer without it as on time", () => {
    const older: Record<string, unknown> = { ...VITALS };
    delete older.synced_late;

    expect(vitalsSchema.parse({ ...VITALS, synced_late: true }).synced_late).toBe(true);
    expect(vitalsSchema.parse(older).synced_late).toBe(false);
  });
});

describe("records api", () => {
  it("starts the visit, then opens its encounter with an ID made on the device", async () => {
    fetchMock.mockImplementationOnce(async () => answer({ id: VISIT }));
    fetchMock.mockImplementationOnce(async () => answer(ENCOUNTER, 201));

    expect(await startVisit(VISIT, PATIENT)).toEqual(ENCOUNTER);
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/appointments/${VISIT}/start`);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/backend/encounters");
    const body = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(body).toMatchObject({ patient_id: PATIENT, appointment_id: VISIT });
    expect(body.id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("gives every new entry its own device ID", async () => {
    fetchMock.mockImplementation(async () => answer(VITALS, 201));

    await recordVitals(ENCOUNTER.id, { pulse_bpm: 88 });
    await recordVitals(ENCOUNTER.id, { pulse_bpm: 88 });

    const first = JSON.parse(fetchMock.mock.calls[0][1].body).id;
    const second = JSON.parse(fetchMock.mock.calls[1][1].body).id;
    expect(first).not.toBe(second);
  });

  it("sends allergy details to the encounter they are recorded in", async () => {
    fetchMock.mockImplementation(async () => answer({}, 500));

    await expect(
      addAllergy(ENCOUNTER.id, {
        substance: "Penicillin",
        reaction: null,
        severity: "unknown",
        clinical_status: "active",
      }),
    ).rejects.toThrow();
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/encounters/${ENCOUNTER.id}/allergies`);
  });

  it("signs off, then completes the visit", async () => {
    fetchMock.mockImplementationOnce(async () => answer({ ...ENCOUNTER, status: "closed" }));
    fetchMock.mockImplementationOnce(async () => answer({ id: VISIT }));

    expect(await signOff(ENCOUNTER)).toEqual({ visitCompleted: true });
    expect(fetchMock.mock.calls[1][0]).toBe(`/api/backend/appointments/${VISIT}/complete`);
  });

  it("still counts as signed off when someone else started the visit", async () => {
    fetchMock.mockImplementationOnce(async () => answer({ ...ENCOUNTER, status: "closed" }));
    fetchMock.mockImplementationOnce(async () => answer({ detail: "Only the clinician..." }, 403));

    expect(await signOff(ENCOUNTER)).toEqual({ visitCompleted: false });
  });

  it("does not try to complete a visit when there is none", async () => {
    fetchMock.mockImplementationOnce(async () => answer({ ...ENCOUNTER, status: "closed" }));

    expect(await signOff({ ...ENCOUNTER, appointment_id: null })).toEqual({ visitCompleted: false });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
