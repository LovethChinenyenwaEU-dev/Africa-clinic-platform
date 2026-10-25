import { notFound } from "next/navigation";

import { InvoiceDetail } from "@/features/billing/InvoiceDetail";
import { can } from "@/features/identity/abilities";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Invoice | Lafiya" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One invoice. Admins read it (to decide refunds); front desk and billing change it.
export default async function InvoicePage({
  params,
}: {
  params: Promise<{ invoiceId: string }>;
}) {
  const user = await requireUser("invoice");
  const { invoiceId } = await params;
  if (!UUID.test(invoiceId)) {
    notFound();
  }
  return <InvoiceDetail invoiceId={invoiceId} canWrite={can(user.role, "take_payments")} />;
}
