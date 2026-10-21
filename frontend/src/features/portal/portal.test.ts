import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

import { confirmCode, getMyVisits, requestCode, splitVisits, type MyVisit } from "./api";
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
