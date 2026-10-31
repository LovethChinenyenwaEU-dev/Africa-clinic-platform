import { beforeEach, describe, expect, it, vi } from "vitest";

import { describeReason, getReminders, retryReminder } from "./api";

const fetchMock = vi.fn();
const ID = "11111111-1111-4111-8111-111111111111";

const CONSOLE = {
  from_day: "2026-11-02",
  to_day: "2026-11-02",
  counts: { pending: 0, sent: 1, failed: 1, cancelled: 0 },
  failures: { no_phone: 1 },
  more: false,
  lines: [
    {
      id: ID,
      appointment_id: "22222222-2222-4222-8222-222222222222",
      channel: "sms",
      status: "failed",
      due_at: "2026-11-02T08:00:00Z",
      attempts: 0,
      last_error: "no_phone",
      sent_at: null,
      visit_starts_at: "2026-11-02T10:00:00Z",
      visit_type: "in_person",
      can_retry: true,
    },
  ],
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

describe("the reminder console", () => {
  it("asks for the chosen days, and one status only when one is chosen", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(answer(CONSOLE)));

    await getReminders("2026-11-01", "2026-11-02", null);
    await getReminders("2026-11-01", "2026-11-02", "failed");

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "/api/backend/notifications/reminders?from_day=2026-11-01&to_day=2026-11-02",
    );
    expect(String(fetchMock.mock.calls[1][0])).toContain("&reminder_status=failed");
  });

  it("refuses an answer of the wrong shape", async () => {
    fetchMock.mockResolvedValueOnce(answer({ ...CONSOLE, lines: [{ id: "x" }] }));

    await expect(getReminders("2026-11-01", "2026-11-02", null)).rejects.toThrow();
  });

  it("tries a failed reminder again, and shows the backend's reason when it cannot", async () => {
    fetchMock.mockResolvedValueOnce(answer({ id: ID, status: "pending", due_at: "x" }));
    fetchMock.mockResolvedValueOnce(answer({ detail: "The visit is no longer booked." }, 409));

    await retryReminder(ID);
    await expect(retryReminder(ID)).rejects.toThrow(/no longer booked/);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `/api/backend/notifications/reminders/${ID}/retry`,
    );
  });

  it("says each failure reason in words, and shows an unknown code as it is", () => {
    expect(describeReason("no_phone")).toMatch(/No phone number/);
    expect(describeReason("something_new")).toBe("something_new");
    expect(describeReason(null)).toBe("");
  });
});
