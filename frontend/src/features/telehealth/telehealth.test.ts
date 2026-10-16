import { beforeEach, describe, expect, it, vi } from "vitest";

import { isRead } from "@/features/audit/labels";

import { getTeleconsultStatus, submitIntake } from "./api";

const fetchMock = vi.fn();
const VISIT = "22222222-2222-4222-8222-222222222222";

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

describe("teleconsult intake", () => {
  it("sends the reason and danger signs with an ID made on the device", async () => {
    fetchMock.mockResolvedValueOnce(
      answer(
        {
          id: "33333333-3333-4333-8333-333333333333",
          appointment_id: VISIT,
          outcome: "escalated",
          red_flags: ["chest_pain"],
          recorded_at: "2026-11-02T08:00:00Z",
          advice: "This needs in-person care.",
        },
        201,
      ),
    );

    const result = await submitIntake(VISIT, "Chest tightness", ["chest_pain"]);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`/api/backend/teleconsults/${VISIT}/intake`);
    const body = JSON.parse(init.body);
    expect(body).toMatchObject({ reason: "Chest tightness", red_flags: ["chest_pain"] });
    expect(body.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(result.outcome).toBe("escalated");
    expect(result.advice).toContain("in-person");
  });

  it("reads whether the patient consented and what the intake decided", async () => {
    fetchMock.mockResolvedValueOnce(answer({ consented: false, intake: null }));

    expect(await getTeleconsultStatus(VISIT)).toEqual({ consented: false, intake: null });
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/teleconsults/${VISIT}/status`);
  });

  it("counts reading an intake as a look in the audit log", () => {
    expect(isRead("teleconsult.intake_view")).toBe(true);
    expect(isRead("teleconsult.intake")).toBe(false);
  });
});
