import { z } from "zod";

// Mirrors backend/app/modules/reports/schemas.py. Counts and sums only: no patient details.

const count = z.number().int().nonnegative();
const rate = z.number().min(0).max(1).nullable();

export const dashboardSchema = z.object({
  from_day: z.string(),
  to_day: z.string(),
  visits: z.object({
    total: count,
    walk_ins: count,
    done: count,
    no_shows: count,
    cancelled: count,
    still_open: count,
    checked_in: count,
    no_show_rate: rate,
    completion_rate: rate,
  }),
  waits: z.object({
    measured: count,
    median_minutes: z.number().nullable(),
    p90_minutes: z.number().nullable(),
    over_an_hour: count,
  }),
  revenue: z.object({
    invoices_issued: count,
    billed_kobo: z.number().int(),
    payments: count,
    received_kobo: z.number().int(),
    refunds: count,
    refunded_kobo: z.number().int(),
    net_kobo: z.number().int(),
    by_method: z.array(
      z.object({ method: z.string(), count, amount_kobo: z.number().int() }),
    ),
  }),
  sync: z.object({
    late_entries: count,
    open_conflicts: count,
    registrations_to_review: count,
    reminders_sent: count,
    reminders_failed: count,
    online_payments_failed: count,
  }),
  record_access: z.object({
    events: count,
    patients: count,
    by_staff: z.array(
      z.object({ staff_id: z.string().uuid(), name: z.string(), events: count, patients: count }),
    ),
  }),
  days: z.array(
    z.object({
      day: z.string(),
      visits: count,
      done: count,
      no_shows: count,
      median_wait_minutes: z.number().nullable(),
      received_kobo: z.number().int(),
    }),
  ),
});

export type Dashboard = z.infer<typeof dashboardSchema>;
export type DashboardDay = Dashboard["days"][number];
