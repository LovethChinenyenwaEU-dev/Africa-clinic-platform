import { beforeEach, describe, expect, it, vi } from "vitest";

import { getCurrentWording, recordConsent, withdrawConsent } from "./api";
import type { Consent } from "./schemas";
import { currentConsent } from "./status";

const PATIENT = "11111111-1111-4111-8111-111111111111";
const fetchMock = vi.fn();

function consent(purpose: string, grantedAt: string, revokedAt: string | null = null): Consent {
  return {
    id: crypto.randomUUID(),
    patient_id: PATIENT,
    purpose,
    wording_version: 1,
    granted_by: "patient",
    granted_at: grantedAt,
    revoked_at: revokedAt,
  };
}

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

describe("currentConsent", () => {
  it("marks every purpose not recorded when there is no history", () => {
    const now = currentConsent([]);

    expect(Object.values(now).map((entry) => entry.state)).toEqual([
      "not_recorded",
      "not_recorded",
      "not_recorded",
      "not_recorded",
    ]);
  });

  it("lets the newest record for a purpose decide", () => {
    const withdrawn = consent("reminders", "2026-01-01T09:00:00Z", "2026-02-01T09:00:00Z");
    const agreedAgain = consent("reminders", "2026-03-01T09:00:00Z");
    const treatment = consent("treatment", "2026-01-01T09:00:00Z");

    const now = currentConsent([withdrawn, treatment, agreedAgain]);

    expect(now.reminders).toEqual({ state: "agreed", consent: agreedAgain });
    expect(now.treatment).toEqual({ state: "agreed", consent: treatment });
    expect(now.teleconsult).toEqual({ state: "not_recorded" });
  });

  it("shows a withdrawn agreement as withdrawn", () => {
    const withdrawn = consent("teleconsult", "2026-01-01T09:00:00Z", "2026-02-01T09:00:00Z");

    expect(currentConsent([withdrawn]).teleconsult).toEqual({
      state: "withdrawn",
      consent: withdrawn,
    });
  });
});

describe("consent api", () => {
  it("returns null when the clinic has not published wording yet", async () => {
    fetchMock.mockResolvedValueOnce(answer({ detail: "No consent text..." }, 404));

    expect(await getCurrentWording("reminders")).toBeNull();
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/backend/consent/texts/current?purpose=reminders",
    );
  });

  it("records and withdraws on the right addresses", async () => {
    const agreed = consent("reminders", "2026-03-01T09:00:00Z");
    fetchMock.mockResolvedValueOnce(answer(agreed, 201));
    fetchMock.mockResolvedValueOnce(answer({ ...agreed, revoked_at: "2026-04-01T09:00:00Z" }));

    await recordConsent(PATIENT, "reminders", "caregiver");
    await withdrawConsent(PATIENT, "reminders");

    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/patients/${PATIENT}/consents`);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      purpose: "reminders",
      granted_by: "caregiver",
    });
    expect(fetchMock.mock.calls[1][0]).toBe(
      `/api/backend/patients/${PATIENT}/consents/reminders/revoke`,
    );
  });
});
