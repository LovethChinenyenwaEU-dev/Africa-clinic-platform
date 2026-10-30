import { RefundDecisions } from "@/features/billing/RefundDecisions";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Refunds | AfriPeak Health" };

// Admins decide refunds; never one they asked for (FR-B3).
export default async function RefundsPage() {
  const user = await requireUser("refunds");
  return <RefundDecisions meId={user.id} />;
}
