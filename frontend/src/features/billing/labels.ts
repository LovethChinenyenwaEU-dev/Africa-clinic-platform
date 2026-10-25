// Billing words and badge colours. Text and colour together, never colour alone.

export const INVOICE_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  issued: "Issued",
  void: "Voided",
};

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  not_issued: "Not issued yet",
  unpaid: "Unpaid",
  part_paid: "Part paid",
  paid: "Paid",
  overpaid: "Overpaid: give the difference back",
  refunded: "Refunded",
};

export const PAYMENT_STATUS_STYLES: Record<string, string> = {
  not_issued: "bg-gray-200 text-gray-800",
  unpaid: "bg-red-100 text-red-900",
  part_paid: "bg-amber-100 text-amber-900",
  paid: "bg-green-100 text-green-900",
  overpaid: "bg-amber-100 text-amber-900",
  refunded: "bg-gray-200 text-gray-800",
};

export const METHOD_LABELS: Record<string, string> = {
  cash: "Cash",
  transfer: "Bank transfer",
  paystack: "Paid online (Paystack)",
};

export const REFUND_STATUS_LABELS: Record<string, string> = {
  requested: "Waiting for an admin",
  approved: "Approved",
  rejected: "Rejected",
};

export const LINK_STATUS_LABELS: Record<string, string> = {
  pending: "Waiting for the patient to pay",
  succeeded: "Paid",
  failed: "Failed",
};

export function label(labels: Record<string, string>, value: string): string {
  return labels[value] ?? value;
}
