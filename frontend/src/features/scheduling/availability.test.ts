import { beforeEach, describe, expect, it, vi } from "vitest";

import { bookVisit, getFreeSlots, publishHours, removeHours } from "./api";
import { WEEKDAY_LABELS, clockTime } from "./labels";
import { slotMinutes } from "./VisitForms";

const fetchMock = vi.fn();
const CLINICIAN = "55555555-5555-4555-8555-555555555555";
const BRANCH = "66666666-6666-4666-8666-666666666666";
const HOURS = {
  id: "77777777-7777-4777-8777-777777777777",
  clinician_id: CLINICIAN,
  branch_id: BRANCH,
  weekday: 0,
  starts: "09:00:00",
  ends: "13:00:00",
  visit_type: "teleconsult",
  slot_minutes: 15,
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

describe("weekly hours", () => {
  it("publishes hours with an ID made on the device", async () => {
    fetchMock.mockResolvedValueOnce(answer(HOURS, 201));

    await publishHours({
      branch_id: BRANCH,
      weekday: 0,
      starts: "09:00",
      ends: "13:00",
      visit_type: "teleconsult",
      slot_minutes: 15,
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/backend/availability");
    expect(JSON.parse(init.body)).toMatchObject({ weekday: 0, starts: "09:00", slot_minutes: 15 });
    expect(JSON.parse(init.body).id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("removes hours with a POST, like every other action", async () => {
    fetchMock.mockResolvedValueOnce(answer(HOURS));

    await removeHours(HOURS.id);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`/api/backend/availability/${HOURS.id}/remove`);
    expect(init.method).toBe("POST");
  });

  it("asks for free slots with every filter in the address", async () => {
    fetchMock.mockResolvedValueOnce(answer([]));

    await getFreeSlots(CLINICIAN, "teleconsult", "2026-11-02");

    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/backend/availability/slots?clinician_id=${CLINICIAN}&visit_type=teleconsult&from_day=2026-11-02&days=7`,
    );
  });

  it("shows Monday first and clock times without seconds", () => {
    expect(WEEKDAY_LABELS[0]).toBe("Monday");
    expect(clockTime("09:30:00")).toBe("09:30");
  });
});

describe("booking a free slot", () => {
  it("books exactly the slot's length, as the chosen kind of visit", async () => {
    const slot = { starts_at: "2026-11-02T08:00:00Z", ends_at: "2026-11-02T08:15:00Z" };
    fetchMock.mockResolvedValueOnce(answer({}, 500)); // only the request matters here

    await bookVisit({
      patient_id: "11111111-1111-4111-8111-111111111111",
      branch_id: BRANCH,
      clinician_id: CLINICIAN,
      visit_type: "teleconsult",
      starts_at: slot.starts_at,
      duration_minutes: slotMinutes(slot),
    }).catch(() => {});

    expect(slotMinutes(slot)).toBe(15);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      visit_type: "teleconsult",
      duration_minutes: 15,
    });
  });
});
