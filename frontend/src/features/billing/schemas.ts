import { z } from "zod";

// The billing answers from the API (backend/app/modules/billing/schemas.py). Money is
// always whole kobo.

const kobo = z.number().int();
const id = z.string().uuid();
const moment = z.string();

export const priceSchema = z.object({
  id,
  name: z.string(),
  code: z.string().nullable(),
  price_kobo: kobo,
  active: z.boolean(),
  created_at: moment,
  updated_at: moment.nullable(),
});
export type Price = z.infer<typeof priceSchema>;

export const invoiceLineSchema = z.object({
  id,
  price_item_id: id,
  description: z.string(),
  unit_price_kobo: kobo,
  quantity: z.number().int(),
  amount_kobo: kobo,
  added_at: moment,
});
export type InvoiceLine = z.infer<typeof invoiceLineSchema>;

export const paymentSchema = z.object({
  id,
  invoice_id: id,
  method: z.string(),
  amount_kobo: kobo,
  reference: z.string().nullable(),
  receipt_number: z.string(),
  received_by_id: id,
  received_at: moment,
});
export type Payment = z.infer<typeof paymentSchema>;

export const refundSchema = z.object({
  id,
  invoice_id: id,
  payment_id: id,
  patient_id: id,
  amount_kobo: kobo,
  method: z.string(),
  reason: z.string(),
  status: z.string(),
  refund_number: z.string().nullable(),
  requested_by_id: id,
  requested_at: moment,
  decided_by_id: id.nullable(),
  decided_at: moment.nullable(),
  decision_note: z.string().nullable(),
});
export type Refund = z.infer<typeof refundSchema>;

export const onlinePaymentSchema = z.object({
  id,
  invoice_id: id,
  gateway: z.string(),
  reference: z.string(),
  amount_kobo: kobo,
  link: z.string(),
  status: z.string(),
  failure_reason: z.string().nullable(),
  payment_id: id.nullable(),
  created_at: moment,
  completed_at: moment.nullable(),
});
export type OnlinePayment = z.infer<typeof onlinePaymentSchema>;

export const invoiceSummarySchema = z.object({
  id,
  patient_id: id,
  appointment_id: id,
  status: z.string(), // draft, issued or void
  number: z.string().nullable(),
  total_kobo: kobo,
  created_at: moment,
  issued_at: moment.nullable(),
  voided_at: moment.nullable(),
  void_reason: z.string().nullable(),
  paid_kobo: kobo,
  refunded_kobo: kobo,
  balance_kobo: kobo,
  credit_kobo: kobo,
  payment_status: z.string(), // not_issued, unpaid, part_paid, paid, overpaid or refunded
});
export type InvoiceSummary = z.infer<typeof invoiceSummarySchema>;

export const invoiceSchema = invoiceSummarySchema.extend({
  lines: z.array(invoiceLineSchema),
  payments: z.array(paymentSchema),
  refunds: z.array(refundSchema),
  online_payments: z.array(onlinePaymentSchema),
});
export type Invoice = z.infer<typeof invoiceSchema>;

export const visitToBillSchema = z.object({
  appointment_id: id,
  starts_at: moment,
  status: z.string(),
  visit_type: z.string(),
  invoice: invoiceSummarySchema.nullable(),
});
export type VisitToBill = z.infer<typeof visitToBillSchema>;

export const receiptSchema = z.object({
  payment: paymentSchema,
  clinic_name: z.string(),
  patient_name: z.string(),
  invoice_number: z.string(),
  invoice_total_kobo: kobo,
  paid_to_date_kobo: kobo,
  balance_after_kobo: kobo,
  received_by_name: z.string(),
  check_code: z.string(),
});
export type Receipt = z.infer<typeof receiptSchema>;

export const methodTotalSchema = z.object({ method: z.string(), count: z.number().int(), amount_kobo: kobo });
export type MethodTotal = z.infer<typeof methodTotalSchema>;

export const takingsSchema = z.object({
  day: z.string(), // "YYYY-MM-DD", a Lagos day
  money_in: z.array(methodTotalSchema),
  money_out: z.array(methodTotalSchema),
  net_by_method: z.array(methodTotalSchema),
  total_in_kobo: kobo,
  total_out_kobo: kobo,
  net_kobo: kobo,
  by_staff: z.array(
    z.object({ staff_id: id, name: z.string(), payments: z.number().int(), taken_kobo: kobo }),
  ),
  invoices_issued: z.number().int(),
  billed_kobo: kobo,
  flags: z.array(
    z.object({
      kind: z.string(),
      message: z.string(),
      invoice_number: z.string().nullable(),
      amount_kobo: kobo.nullable(),
    }),
  ),
});
export type Takings = z.infer<typeof takingsSchema>;

export const takingsExportSchema = z.object({ filename: z.string(), csv: z.string() });
