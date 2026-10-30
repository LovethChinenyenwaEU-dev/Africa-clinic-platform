import { TakingsView } from "@/features/billing/TakingsView";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Daily takings | AfriPeak Health" };

// One Lagos day's money and what to look at: admins and billing.
export default async function TakingsPage() {
  await requireUser("takings");
  return <TakingsView />;
}
