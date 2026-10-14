import { beforeEach, describe, expect, it, vi } from "vitest";

import { bookVisit, changeVisit, getDayList, getQueue, registerWalkIn } from "./api";

const fetchMock = vi.fn();
const BRANCH = "11111111-1111-4111-8111-111111111111";
const PATIENT = "22222222-2222-4222-8222-222222222222";
const VISIT = "33333333-3333-4333-8333-333333333333";
const APPOINTMENT = { id: VISIT, patient_id: PATIENT, status: "waiting", starts_at: "2026-11-02T08:00:00Z" };

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

describe("scheduling api", () => {
  it("reads the queue and the day list for one branch", async () => {
    fetchMock.mockImplementation(async () => answer([]));

    await getQueue(BRANCH);
    await getDayList(BRANCH, "2026-11-02");

    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/appointments/queue?branch_id=${BRANCH}`);
    expect(fetchMock.mock.calls[1][0]).toBe(
      `/api/backend/appointments/day?branch_id=${BRANCH}&date=2026-11-02`,
    );
  });

  it("registers a walk-in, with or without a clinician", async () => {
    fetchMock.mockImplementation(async () => answer(APPOINTMENT, 201));

    await registerWalkIn({ patient_id: PATIENT, branch_id: BRANCH, clinician_id: null });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/backend/appointments/walk-ins");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      patient_id: PATIENT,
      branch_id: BRANCH,
      clinician_id: null,
    });
  });

  it("books a visit with its Lagos time zone", async () => {
    fetchMock.mockImplementation(async () => answer({ ...APPOINTMENT, status: "booked" }, 201));

    await bookVisit({
      patient_id: PATIENT,
      branch_id: BRANCH,
      clinician_id: VISIT,
      starts_at: "2026-11-03T09:00:00+01:00",
    });

    expect(JSON.parse(fetchMock.mock.calls[0][1].body).starts_at).toBe("2026-11-03T09:00:00+01:00");
  });

  it.each(["check-in", "cancel", "no-show"] as const)("sends %s to its own address", async (action) => {
    fetchMock.mockImplementation(async () => answer(APPOINTMENT));

    await changeVisit(VISIT, action);

    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/appointments/${VISIT}/${action}`);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });
});
