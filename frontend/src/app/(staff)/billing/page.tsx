import { BillingDesk } from "@/features/billing/BillingDesk";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Billing | Lafiya" };

// Front desk and billing find a patient's visits and bill them (Week 10).
export default async function BillingPage() {
  await requireUser("billing");
  return <BillingDesk />;
}
