import { Dashboard } from "@/features/reports/Dashboard";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Clinic dashboard | AfriPeak Health" };

// Counts and sums only, for admins (Week 11, P-11).
export default async function DashboardPage() {
  await requireUser("dashboard");
  return <Dashboard />;
}
