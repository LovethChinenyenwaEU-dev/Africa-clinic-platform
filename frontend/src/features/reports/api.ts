import { apiGet } from "@/lib/api-client";

import { dashboardSchema, type Dashboard } from "./schemas";

const q = encodeURIComponent;

/** The clinic's numbers for these Lagos days, both included ("YYYY-MM-DD"). */
export function getDashboard(fromDay: string, toDay: string): Promise<Dashboard> {
  return apiGet(`/reports/dashboard?from_day=${q(fromDay)}&to_day=${q(toDay)}`, dashboardSchema);
}
