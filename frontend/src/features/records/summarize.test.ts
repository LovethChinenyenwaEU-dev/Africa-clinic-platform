import { beforeEach, describe, expect, it, vi } from "vitest";

import { approveSummary, editSummary, startSummary } from "./api";
import type { FollowUp, Prescription, Problem, Referral } from "./schemas";
import { draftFromVisit, type VisitRecord } from "./summarize";

const ENCOUNTER = "33333333-3333-4333-8333-333333333333";
const OTHER_ENCOUNTER = "44444444-4444-4444-8444-444444444444";
const PATIENT = "11111111-1111-4111-8111-111111111111";
const STAFF = "55555555-5555-4555-8555-555555555555";
const fetchMock = vi.fn();

const base = { patient_id: PATIENT, recorded_by_id: STAFF, recorded_at: "2026-11-02T09:00:00Z" };

function problem(description: string, changes: Partial<Problem> = {}): Problem {
  return {
    ...base,
    id: crypto.randomUUID(),
    encounter_id: ENCOUNTER,
    version_status: "current",
    replaces_id: null,
    category: "encounter_diagnosis",
    description,
    code: null,
    clinical_status: "active",
    onset_date: null,
    ...changes,
  };
}

function medicine(changes: Partial<Prescription> = {}): Prescription {
  return {
    ...base,
    id: crypto.randomUUID(),
    encounter_id: ENCOUNTER,
    version_status: "current",
    replaces_id: null,
    medicine: "Artemether-lumefantrine",
    strength: "20/120 mg",
    dose: "4 tablets",
    route: "oral",
    frequency: "twice daily",
    duration: "3 days",
    instructions: "Take with food",
    clinical_status: "active",
    written_at: base.recorded_at,
    synced_late: false,
    ...changes,
  };
}

const FOLLOW_UP: FollowUp = {
  ...base,
  id: crypto.randomUUID(),
  encounter_id: ENCOUNTER,
  due_date: "2026-11-16",
  visit_type: "teleconsult",
  instructions: "Repeat BP", // clinical: not for the patient's summary
  status: "planned",
  appointment_id: null,
  synced_late: false,
};

const REFERRAL: Referral = {
  ...base,
  id: crypto.randomUUID(),
  encounter_id: ENCOUNTER,
  to_name: "LUTH Cardiology clinic",
  specialty: "Cardiology",
  urgency: "urgent",
  reason: "Chest pain on exertion", // the letter's words, not the patient's summary
  status: "active",
  written_at: base.recorded_at,
  synced_late: false,
};

function visit(changes: Partial<VisitRecord> = {}): VisitRecord {
  return {
    visitDay: "2026-11-02T08:30:00Z",
    encounterId: ENCOUNTER,
    problems: [problem("Uncomplicated malaria")],
    prescriptions: [medicine()],
    followUps: [FOLLOW_UP],
    referrals: [REFERRAL],
    ...changes,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("draftFromVisit", () => {
  it("writes a first draft in plain sections", () => {
    const text = draftFromVisit(visit());

    expect(text).toContain("What we found:\n- Uncomplicated malaria");
    expect(text).toContain(
      "- Artemether-lumefantrine 20/120 mg, 4 tablets by mouth, twice daily for 3 days. Take with food",
    );
    expect(text).toContain("by remote consultation");
    expect(text).toContain("referred to LUTH Cardiology clinic (Cardiology) (please go within");
    expect(text).toMatch(/emergency department\.$/); // always ends with when to seek help
  });

  it("leaves out the clinicians' own words: follow-up instructions and referral reasons", () => {
    const text = draftFromVisit(visit());

    expect(text).not.toContain("Repeat BP");
    expect(text).not.toContain("Chest pain on exertion");
  });

  it("uses only this visit's diagnoses, and only what is current and active", () => {
    const text = draftFromVisit(
      visit({
        problems: [
          problem("Malaria"),
          problem("Old asthma", { encounter_id: OTHER_ENCOUNTER }),
          problem("Typo", { clinical_status: "entered_in_error" }),
          problem("First wording", { version_status: "superseded" }),
        ],
        prescriptions: [medicine({ clinical_status: "stopped" })],
        followUps: [{ ...FOLLOW_UP, status: "cancelled" }],
        referrals: [{ ...REFERRAL, status: "cancelled" }],
      }),
    );

    expect(text).toContain("- Malaria");
    expect(text).not.toMatch(/Old asthma|Typo|First wording|Your medicines|What happens next/);
  });

  it("names the visit by its Lagos day, even just after midnight UTC", () => {
    expect(draftFromVisit(visit({ visitDay: "2026-11-02T23:30:00Z" }))).toContain("3 Nov 2026");
  });
});

describe("summary calls", () => {
  it("start, edit and approve go to the right places", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 500 }));

    await startSummary(ENCOUNTER, "Hello").catch(() => {});
    await editSummary("s1", "Hello again").catch(() => {});
    await approveSummary("s1").catch(() => {});

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      `/api/backend/encounters/${ENCOUNTER}/summaries`,
      "/api/backend/summaries/s1/draft",
      "/api/backend/summaries/s1/approve",
    ]);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).id).toMatch(/^[0-9a-f-]{36}$/);
  });
});
