import { beforeEach, describe, expect, it, vi } from "vitest";

import { getFollowUpsDue, markFollowUpBooked } from "@/features/scheduling/api";
import { lagosDayPlus } from "@/features/scheduling/FollowUpsDue";
import { followUpDueSchema } from "@/features/scheduling/schemas";
import { keepsOffline } from "@/lib/sync/read-cache";

import { cancelReferral, followUpWrite, referralWrite } from "./api";

const fetchMock = vi.fn();
const ENCOUNTER = "33333333-3333-4333-8333-333333333333";
const WHEN = new Date("2026-11-02T09:30:00Z");

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("follow-up and referral writes", () => {
  it("queue a follow-up with its own ID and the device time", () => {
    const write = followUpWrite(
      ENCOUNTER,
      { due_date: "2026-11-16", visit_type: "teleconsult", instructions: "Repeat BP" },
      WHEN,
    );

    expect(write).toMatchObject({
      path: `/encounters/${ENCOUNTER}/follow-ups`,
      body: { due_date: "2026-11-16", visit_type: "teleconsult", written_at: WHEN.toISOString() },
      label: "Follow-up",
      encounterId: ENCOUNTER,
    });
    expect((write.body as { id: string }).id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("queue a referral labelled plainly, never with its content", () => {
    const write = referralWrite(
      ENCOUNTER,
      { to_name: "LUTH Cardiology", specialty: null, urgency: "urgent", reason: "Chest pain" },
      WHEN,
    );

    expect(write.path).toBe(`/encounters/${ENCOUNTER}/referrals`);
    expect(write.label).toBe("Referral");
    expect(write.label).not.toContain("LUTH");
  });

  it("cancel a referral directly", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 500 }));

    await cancelReferral("r1").catch(() => {});

    expect(fetchMock.mock.calls[0][0]).toBe("/api/backend/referrals/r1/cancel");
  });

  it("are kept for offline reading like the rest of the encounter", () => {
    expect(keepsOffline(["follow-ups", ENCOUNTER], new Set())).toBe(true);
    expect(keepsOffline(["referrals", ENCOUNTER], new Set())).toBe(true);
  });
});

describe("follow-ups due (front desk)", () => {
  it("counts days on the Lagos calendar, across months", () => {
    expect(lagosDayPlus(14, "2026-11-20")).toBe("2026-12-04");
    expect(lagosDayPlus(0, "2026-12-31")).toBe("2026-12-31");
    expect(lagosDayPlus(1, "2026-12-31")).toBe("2027-01-01");
  });

  it("asks for those due by a day, and marks one booked", async () => {
    fetchMock.mockResolvedValue(new Response("[]", { status: 200 }));

    await getFollowUpsDue("2026-12-04");
    await markFollowUpBooked("f1").catch(() => {});

    expect(fetchMock.mock.calls[0][0]).toBe("/api/backend/follow-ups/due?until=2026-12-04");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/backend/follow-ups/f1/booked");
  });

  it("carry no clinical instructions", () => {
    expect(Object.keys(followUpDueSchema.shape)).not.toContain("instructions");
  });
});
