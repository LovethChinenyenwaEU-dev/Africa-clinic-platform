import { z } from "zod";

import { apiGet, apiPost } from "@/lib/api-client";

import {
  invoiceSchema,
  onlinePaymentSchema,
  paymentSchema,
  priceSchema,
  receiptSchema,
  refundSchema,
  takingsExportSchema,
  takingsSchema,
  visitToBillSchema,
  type Invoice,
  type OnlinePayment,
  type Payment,
  type Price,
  type Receipt,
  type Refund,
  type Takings,
  type VisitToBill,
} from "./schemas";

// Every write carries a fresh ID: if the network repeats the request, the server
// recognises it and does the work once (a payment is never taken twice).
const newId = () => crypto.randomUUID();
const q = encodeURIComponent;

// --- the price list ------------------------------------------------------------

export function getPrices(includeRetired = false): Promise<Price[]> {
  const query = includeRetired ? "?include_retired=true" : "";
  return apiGet(`/billing/prices${query}`, z.array(priceSchema));
}

export type PriceForm = { name: string; code: string; price_kobo: number };

export function addPrice(form: PriceForm): Promise<Price> {
  return apiPost(
    "/billing/prices",
    { id: newId(), name: form.name, code: form.code || null, price_kobo: form.price_kobo },
    priceSchema,
  );
}

export function changePrice(price: Price, changes: Partial<PriceForm & { active: boolean }>) {
  const body = {
    name: changes.name ?? price.name,
    code: (changes.code ?? price.code) || null,
    price_kobo: changes.price_kobo ?? price.price_kobo,
    active: changes.active ?? price.active,
  };
  return apiPost(`/billing/prices/${q(price.id)}`, body, priceSchema);
}

// --- invoices --------------------------------------------------------------------

/** A patient's recent visits with their invoices. One diary line per look. */
export function getVisitsToBill(patientId: string): Promise<VisitToBill[]> {
  return apiGet(`/billing/patients/${q(patientId)}/visits`, z.array(visitToBillSchema));
}

/** Start the visit's invoice, or get the one it already has. */
export function startInvoice(appointmentId: string): Promise<Invoice> {
  return apiPost(
    "/billing/invoices",
    { id: newId(), appointment_id: appointmentId },
    invoiceSchema,
  );
}

export function getInvoice(invoiceId: string): Promise<Invoice> {
  return apiGet(`/billing/invoices/${q(invoiceId)}`, invoiceSchema);
}

export function addInvoiceLine(invoiceId: string, priceItemId: string, quantity: number) {
  return apiPost(
    `/billing/invoices/${q(invoiceId)}/lines`,
    { id: newId(), price_item_id: priceItemId, quantity },
    invoiceSchema,
  );
}

export function removeInvoiceLine(invoiceId: string, lineId: string): Promise<Invoice> {
  return apiPost(`/billing/invoices/${q(invoiceId)}/lines/${q(lineId)}/remove`, {}, invoiceSchema);
}

export function issueInvoice(invoiceId: string): Promise<Invoice> {
  return apiPost(`/billing/invoices/${q(invoiceId)}/issue`, {}, invoiceSchema);
}

export function voidInvoice(invoiceId: string, reason: string): Promise<Invoice> {
  return apiPost(`/billing/invoices/${q(invoiceId)}/void`, { reason }, invoiceSchema);
}

// --- money in and out ---------------------------------------------------------------

export type PaymentForm = { method: "cash" | "transfer"; amount_kobo: number; reference: string };

export function recordPayment(invoiceId: string, form: PaymentForm): Promise<Payment> {
  return apiPost(
    `/billing/invoices/${q(invoiceId)}/payments`,
    {
      id: newId(),
      method: form.method,
      amount_kobo: form.amount_kobo,
      reference: form.reference.trim() || null,
    },
    paymentSchema,
  );
}

export function getReceipt(paymentId: string): Promise<Receipt> {
  return apiGet(`/billing/payments/${q(paymentId)}/receipt`, receiptSchema);
}

export type RefundForm = { amount_kobo: number; method: "cash" | "transfer"; reason: string };

export function requestRefund(paymentId: string, form: RefundForm): Promise<Refund> {
  return apiPost(
    `/billing/payments/${q(paymentId)}/refunds`,
    { id: newId(), ...form },
    refundSchema,
  );
}

/** A Paystack link. No amount: everything still owed. */
export function sendPaymentLink(
  invoiceId: string,
  form: { amount_kobo?: number; email?: string },
): Promise<OnlinePayment> {
  return apiPost(
    `/billing/invoices/${q(invoiceId)}/online-payments`,
    { id: newId(), amount_kobo: form.amount_kobo ?? null, email: form.email?.trim() || null },
    onlinePaymentSchema,
  );
}

export function checkPaymentLink(onlineId: string): Promise<OnlinePayment> {
  return apiPost(`/billing/online-payments/${q(onlineId)}/check`, {}, onlinePaymentSchema);
}

// --- refund decisions (admins) ------------------------------------------------------

/** The clinic's refunds: waiting ones by default. One diary line per look. */
export function getRefunds(status: "requested" | "approved" | "rejected" = "requested") {
  return apiGet(`/billing/refunds?status=${q(status)}`, z.array(refundSchema));
}

export function approveRefund(refundId: string, note: string): Promise<Refund> {
  return apiPost(
    `/billing/refunds/${q(refundId)}/approve`,
    { note: note.trim() || null },
    refundSchema,
  );
}

export function rejectRefund(refundId: string, note: string): Promise<Refund> {
  return apiPost(`/billing/refunds/${q(refundId)}/reject`, { note: note.trim() }, refundSchema);
}

// --- the daily takings (admins and billing) -------------------------------------------

export function getTakings(day: string): Promise<Takings> {
  return apiGet(`/billing/takings?day=${q(day)}`, takingsSchema);
}

/** The day as CSV. It comes inside JSON (the pass-through only carries JSON). */
export function exportTakings(day: string): Promise<{ filename: string; csv: string }> {
  return apiGet(`/billing/takings/export?day=${q(day)}`, takingsExportSchema);
}
