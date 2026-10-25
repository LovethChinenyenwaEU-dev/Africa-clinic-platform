import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  changePrice,
  getPrices,
  getVisitsToBill,
  recordPayment,
  requestRefund,
  sendPaymentLink,
} from "./api";
import { label, PAYMENT_STATUS_LABELS } from "./labels";
import { invoiceSchema, visitToBillSchema, type Price } from "./schemas";

const ID = "11111111-1111-4111-8111-111111111111";
const NOW = "2026-11-02T09:00:00+00:00";

const summary = {
  id: ID,
  patient_id: ID,
  appointment_id: ID,
  status: "issued",
  number: "INV-000001",
  total_kobo: 650_000,
  created_at: NOW,
  issued_at: NOW,
  voided_at: null,
  void_reason: null,
  paid_kobo: 500_000,
  refunded_kobo: 0,
  balance_kobo: 150_000,
  credit_kobo: 0,
  payment_status: "part_paid",
};

const payment = {
  id: ID,
  invoice_id: ID,
  method: "cash",
  amount_kobo: 500_000,
  reference: null,
  receipt_number: "RCT-000001",
  received_by_id: ID,
  received_at: NOW,
};

const price: Price = {
  id: ID,
  name: "Consult",
  code: "CONS",
  price_kobo: 500_000,
  active: true,
  created_at: NOW,
  updated_at: null,
};

const fetchMock = vi.fn();

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function sent(call = 0): { url: string; body: Record<string, unknown> } {
  const [url, init] = fetchMock.mock.calls[call];
  return { url, body: init.body ? JSON.parse(init.body) : {} };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("billing schemas", () => {
  it("read a full invoice with its lines, payments, refunds and links", () => {
    const parsed = invoiceSchema.parse({
      ...summary,
      lines: [
        {
          id: ID,
          price_item_id: ID,
          description: "Consult",
          unit_price_kobo: 500_000,
          quantity: 1,
          amount_kobo: 500_000,
          added_at: NOW,
        },
      ],
      payments: [payment],
      refunds: [],
      online_payments: [
        {
          id: ID,
          invoice_id: ID,
          gateway: "paystack",
          reference: "LFY-abc",
          amount_kobo: 150_000,
          link: "https://checkout.paystack.com/x",
          status: "pending",
          failure_reason: null,
          payment_id: null,
          created_at: NOW,
          completed_at: null,
        },
      ],
    });

    expect(parsed.balance_kobo).toBe(150_000);
    expect(parsed.online_payments[0].status).toBe("pending");
  });

  it("refuse money that is not whole kobo", () => {
    expect(invoiceSchema.safeParse({ ...summary, total_kobo: 6500.5 }).success).toBe(false);
  });

  it("read a visit with no invoice yet", () => {
    const visit = visitToBillSchema.parse({
      appointment_id: ID,
      starts_at: NOW,
      status: "done",
      visit_type: "in_person",
      invoice: null,
    });
    expect(visit.invoice).toBeNull();
  });
});

describe("billing calls", () => {
  it("only asks for retired services when told to", async () => {
    fetchMock.mockImplementation(async () => answer([price])); // a fresh answer each time

    await getPrices();
    await getPrices(true);

    expect(sent(0).url).toBe("/api/backend/billing/prices");
    expect(sent(1).url).toBe("/api/backend/billing/prices?include_retired=true");
  });

  it("sends the whole service when one thing changes", async () => {
    fetchMock.mockResolvedValueOnce(answer({ ...price, active: false }));

    await changePrice(price, { active: false });

    expect(sent().body).toEqual({
      name: "Consult",
      code: "CONS",
      price_kobo: 500_000,
      active: false,
    });
  });

  it("reads a patient's visits through the billing door", async () => {
    fetchMock.mockResolvedValueOnce(answer([]));

    await getVisitsToBill(ID);

    expect(sent().url).toBe(`/api/backend/billing/patients/${ID}/visits`);
  });

  it("sends a payment with its own ID and no empty reference", async () => {
    fetchMock.mockResolvedValueOnce(answer(payment, 201));

    await recordPayment(ID, { method: "cash", amount_kobo: 500_000, reference: "  " });

    const { url, body } = sent();
    expect(url).toBe(`/api/backend/billing/invoices/${ID}/payments`);
    expect(body).toMatchObject({ method: "cash", amount_kobo: 500_000, reference: null });
    expect(body.id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("asks a payment link for everything owed when no amount is given", async () => {
    fetchMock.mockResolvedValueOnce(
      answer({
        id: ID,
        invoice_id: ID,
        gateway: "paystack",
        reference: "LFY-1",
        amount_kobo: 150_000,
        link: "https://checkout.paystack.com/x",
        status: "pending",
        failure_reason: null,
        payment_id: null,
        created_at: NOW,
        completed_at: null,
      }, 201),
    );

    await sendPaymentLink(ID, { email: "" });

    expect(sent().body).toMatchObject({ amount_kobo: null, email: null });
  });

  it("sends a refund request for one payment", async () => {
    fetchMock.mockResolvedValueOnce(
      answer({
        id: ID,
        invoice_id: ID,
        payment_id: ID,
        patient_id: ID,
        amount_kobo: 100_000,
        method: "cash",
        reason: "Test not done",
        status: "requested",
        refund_number: null,
        requested_by_id: ID,
        requested_at: NOW,
        decided_by_id: null,
        decided_at: null,
        decision_note: null,
      }, 201),
    );

    await requestRefund(ID, { amount_kobo: 100_000, method: "cash", reason: "Test not done" });

    expect(sent().url).toBe(`/api/backend/billing/payments/${ID}/refunds`);
    expect(sent().body).toMatchObject({ amount_kobo: 100_000, reason: "Test not done" });
  });
});

describe("labels", () => {
  it("falls back to the raw word for anything new", () => {
    expect(label(PAYMENT_STATUS_LABELS, "part_paid")).toBe("Part paid");
    expect(label(PAYMENT_STATUS_LABELS, "something_new")).toBe("something_new");
  });
});
