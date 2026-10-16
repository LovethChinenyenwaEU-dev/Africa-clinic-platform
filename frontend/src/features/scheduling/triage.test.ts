import { beforeEach, describe, expect, it, vi } from "vitest";

import { recordTriage } from "./api";
import { RED_FLAG_LABELS, TRIAGE_LABELS, TRIAGE_LEVELS, effectiveLevel } from "./labels";
import { queueEntrySchema } from "./schemas";

const fetchMock = vi.fn();
const VISIT = "22222222-2222-4222-8222-222222222222";

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("triage rules on the screen", () => {
  it("makes any danger sign an emergency, like the server", () => {
    expect(effectiveLevel("standard", ["chest_pain"])).toBe("emergency");
    expect(effectiveLevel("urgent", [])).toBe("urgent");
  });

  it("has words for every level and every danger sign the backend knows", () => {
    expect(TRIAGE_LEVELS.every((level) => TRIAGE_LABELS[level])).toBe(true);
    // Mirrors backend RedFlag: 12 codes.
    expect(Object.keys(RED_FLAG_LABELS)).toHaveLength(12);
  });
});

describe("queue entries", () => {
  it("read the triage, and treat an older answer without it as not triaged", () => {
    const entry = {
      appointment_id: VISIT,
      patient_id: "11111111-1111-4111-8111-111111111111",
      patient_name: "Test Patient",
      clinician_id: null,
      kind: "walk_in",
      visit_type: "in_person",
      status: "waiting",
      position: 1,
      scheduled_at: "2026-11-02T08:00:00Z",
      checked_in_at: "2026-11-02T08:00:00Z",
      consult_started_at: null,
      from_earlier_day: false,
    };

    expect(queueEntrySchema.parse(entry)).toMatchObject({ triage_level: null, red_flags: [] });
    expect(
      queueEntrySchema.parse({ ...entry, triage_level: "emergency", red_flags: ["convulsions"] }),
    ).toMatchObject({ triage_level: "emergency", red_flags: ["convulsions"] });
  });
});

describe("recordTriage", () => {
  it("sends codes only, with an ID made on the device", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "33333333-3333-4333-8333-333333333333",
          appointment_id: VISIT,
          level: "emergency",
          red_flags: ["chest_pain"],
          recorded_by_id: "44444444-4444-4444-8444-444444444444",
          recorded_at: "2026-11-02T08:05:00Z",
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      ),
    );

    await recordTriage(VISIT, "standard", ["chest_pain"]);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`/api/backend/appointments/${VISIT}/triage`);
    const body = JSON.parse(init.body);
    expect(body).toMatchObject({ level: "standard", red_flags: ["chest_pain"] });
    expect(body.id).toMatch(/^[0-9a-f-]{36}$/);
  });
});
