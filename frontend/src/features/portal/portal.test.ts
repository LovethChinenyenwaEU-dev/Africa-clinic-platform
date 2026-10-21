import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

import {
  answerIntake,
  bookRemoteVisit,
  confirmCode,
  getMyVisits,
  remoteStep,
  requestCode,
  splitVisits,
  type MyVisit,
} from "./api";
import { patientHome, signInPageFor } from "./paths";

const CLINIC = "11111111-1111-4111-8111-111111111111";
const DETAILS = { clinic_id: CLINIC, phone: "0803 123 4567", date_of_birth: "1990-05-17" };
const fetchMock = vi.fn();

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

describe("where to sign in again", () => {
  it("sends patients back to their clinic's page, and staff to the staff login", () => {
    expect(signInPageFor(`/patient/${CLINIC}/home`)).toBe(`/patient/${CLINIC}`);
    expect(signInPageFor(`/patient/${CLINIC}`)).toBe(`/patient/${CLINIC}`);
    expect(signInPageFor("/encounters/abc")).toBe("/login");
    expect(signInPageFor("/patient/not-a-clinic/home")).toBe("/login");
    expect(patientHome(CLINIC)).toBe(`/patient/${CLINIC}/home`);
  });
});

describe("patient sign-in", () => {
  it("asks for a code through the patient session route, never the staff one", async () => {
    fetchMock.mockResolvedValueOnce(answer({ message: "A code is on its way.", development_code: null }));

    const sent = await requestCode(DETAILS);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/patient-session");
    expect(JSON.parse(init.body)).toEqual({ step: "start", ...DETAILS });
    expect(sent.message).toContain("on its way");
  });

  it("says plainly when the code is wrong or expired", async () => {
    fetchMock.mockResolvedValueOnce(
      answer({ message: "That code is not right, or has expired." }, 401),
    );

    const failure = await confirmCode(DETAILS, "123456").catch((error) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).message).toBe("That code is not right, or has expired.");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      step: "finish",
      code: "123456",
    });
  });
});

describe("the patient's own page", () => {
  it("reads through the patient pass-through", async () => {
    fetchMock.mockResolvedValueOnce(answer([]));

    await getMyVisits();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/patient/visits");
  });

  it("splits visits into to come and past", () => {
    const visit = (endsAt: string): MyVisit => ({
      appointment_id: crypto.randomUUID(),
      starts_at: endsAt,
      ends_at: endsAt,
      visit_type: "in_person",
      status: "booked",
      clinician_name: null,
    });
    const now = new Date("2026-11-02T09:00:00Z");

    const { upcoming, past } = splitVisits(
      [visit("2026-11-03T09:00:00Z"), visit("2026-10-01T09:00:00Z")],
      now,
    );

    expect(upcoming).toHaveLength(1);
    expect(past).toHaveLength(1);
  });
});

describe("remote care on the patient page", () => {
  const remote = (status: string): MyVisit => ({
    appointment_id: crypto.randomUUID(),
    starts_at: "2026-11-02T08:00:00Z",
    ends_at: "2026-11-02T08:30:00Z",
    visit_type: "teleconsult",
    status,
    clinician_name: "Test doctor",
  });

  it("shows the next step of each remote visit, and none for in-person ones", () => {
    expect(remoteStep(remote("booked"))).toBe("intake");
    expect(remoteStep(remote("waiting"))).toBe("waiting");
    expect(remoteStep(remote("in_consult"))).toBe("in_consult");
    expect(remoteStep(remote("done"))).toBeNull();
    expect(remoteStep({ ...remote("booked"), visit_type: "in_person" })).toBeNull();
  });

  it("books a slot and answers the intake with IDs made on the device", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 500 }));
    const slot = {
      clinician_id: "22222222-2222-4222-8222-222222222222",
      clinician_name: "Test doctor",
      starts_at: "2026-11-02T08:00:00Z",
      ends_at: "2026-11-02T08:30:00Z",
    };

    await bookRemoteVisit(slot).catch(() => {});
    await answerIntake("v1", "Cough", ["chest_pain"]).catch(() => {});

    const [bookUrl, bookInit] = fetchMock.mock.calls[0];
    expect(bookUrl).toBe("/api/patient/visits");
    expect(JSON.parse(bookInit.body)).toMatchObject({
      clinician_id: slot.clinician_id,
      starts_at: slot.starts_at,
    });
    expect(JSON.parse(bookInit.body).id).toMatch(/^[0-9a-f-]{36}$/);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/patient/visits/v1/intake");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      reason: "Cough",
      red_flags: ["chest_pain"],
    });
  });
});
