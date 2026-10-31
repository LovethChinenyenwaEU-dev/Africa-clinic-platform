import { beforeEach, describe, expect, it, vi } from "vitest";

import { getDashboard } from "./api";
import type { Dashboard, DashboardDay } from "./schemas";
import {
  addDays,
  barShares,
  daysIn,
  lastDays,
  minutes,
  percent,
  rangeProblem,
  shortDay,
} from "./view";

const fetchMock = vi.fn();

function day(date: string, visits: number): DashboardDay {
  return {
    day: date,
    visits,
    done: 0,
    no_shows: 0,
    median_wait_minutes: null,
    received_kobo: 0,
  };
}

const ANSWER: Dashboard = {
  from_day: "2026-11-02",
  to_day: "2026-11-02",
  visits: {
    total: 7,
    walk_ins: 1,
    done: 3,
    no_shows: 1,
    cancelled: 1,
    still_open: 2,
    checked_in: 4,
    no_show_rate: 0.25,
    completion_rate: 0.75,
  },
  waits: { measured: 4, median_minutes: 40, p90_minutes: 90, over_an_hour: 1 },
  revenue: {
    invoices_issued: 1,
    billed_kobo: 500_000,
    payments: 1,
    received_kobo: 500_000,
    refunds: 0,
    refunded_kobo: 0,
    net_kobo: 500_000,
    by_method: [{ method: "cash", count: 1, amount_kobo: 500_000 }],
  },
  sync: {
    late_entries: 0,
    open_conflicts: 1,
    registrations_to_review: 0,
    reminders_sent: 3,
    reminders_failed: 0,
    online_payments_failed: 0,
  },
  record_access: {
    events: 5,
    patients: 1,
    by_staff: [
      {
        staff_id: "11111111-1111-4111-8111-111111111111",
        name: "Test front_desk",
        events: 5,
        patients: 1,
      },
    ],
  },
  days: [day("2026-11-02", 7)],
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("choosing the days", () => {
  it("counts back from today, both ends included", () => {
    expect(lastDays(7, "2026-11-02")).toEqual({ from: "2026-10-27", to: "2026-11-02" });
    expect(daysIn("2026-10-27", "2026-11-02")).toBe(7);
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });

  it("refuses what the backend would refuse, before asking it", () => {
    expect(rangeProblem("2026-11-02", "2026-11-02")).toBeNull();
    expect(rangeProblem("2026-01-01", "2026-04-02")).toBeNull(); // 92 days
    expect(rangeProblem("2026-01-01", "2026-04-03")).toMatch(/at most 92/);
    expect(rangeProblem("2026-11-03", "2026-11-02")).toMatch(/must not come after/);
    expect(rangeProblem("", "2026-11-02")).toMatch(/both days/);
  });
});

describe("showing the numbers", () => {
  it("writes rates as whole percentages, and nothing-to-measure as a dash", () => {
    expect(percent(0.253)).toBe("25%");
    expect(percent(1)).toBe("100%");
    expect(percent(null)).toBe("—");
  });

  it("writes waits in minutes, then hours", () => {
    expect(minutes(42.4)).toBe("42 min");
    expect(minutes(60)).toBe("1 h");
    expect(minutes(135)).toBe("2 h 15 min");
    expect(minutes(null)).toBe("—");
  });

  it("sizes each bar against the busiest day", () => {
    expect(barShares([day("2026-11-01", 2), day("2026-11-02", 8), day("2026-11-03", 0)])).toEqual(
      [0.25, 1, 0],
    );
    expect(barShares([day("2026-11-01", 0)])).toEqual([0]);
  });

  it("labels a day briefly", () => {
    expect(shortDay("2026-11-02")).toBe("Mon 2 Nov");
  });
});

describe("getDashboard", () => {
  it("asks the staff pass-through for the chosen days and checks the answer", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(ANSWER), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const answer = await getDashboard("2026-11-02", "2026-11-02");

    expect(answer.visits.no_show_rate).toBe(0.25);
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/api/backend/reports/dashboard?from_day=2026-11-02&to_day=2026-11-02",
    );
  });

  it("refuses an answer of the wrong shape", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ visits: "lots" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(getDashboard("2026-11-02", "2026-11-02")).rejects.toThrow();
  });
});
