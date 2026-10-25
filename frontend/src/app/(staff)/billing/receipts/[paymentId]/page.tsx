import { notFound } from "next/navigation";

import { ReceiptView } from "@/features/billing/ReceiptView";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Receipt | Lafiya" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// A receipt to print. Whoever may read invoices may read receipts.
export default async function ReceiptPage({
  params,
}: {
  params: Promise<{ paymentId: string }>;
}) {
  await requireUser("invoice");
  const { paymentId } = await params;
  if (!UUID.test(paymentId)) {
    notFound();
  }
  return <ReceiptView paymentId={paymentId} />;
}
