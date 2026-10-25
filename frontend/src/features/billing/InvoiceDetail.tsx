"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import {
  addInvoiceLine,
  getInvoice,
  getPrices,
  issueInvoice,
  removeInvoiceLine,
  voidInvoice,
} from "./api";
import {
  INVOICE_STATUS_LABELS,
  METHOD_LABELS,
  PAYMENT_STATUS_LABELS,
  PAYMENT_STATUS_STYLES,
  REFUND_STATUS_LABELS,
  label,
} from "./labels";
import { formatNaira } from "./money";
import { PaymentLinks, RefundAsk, TakePayment } from "./PaymentForms";
import type { Invoice } from "./schemas";

/*
 * One invoice. A draft takes services from the price list and is then issued (numbered
 * and frozen) or voided with a reason. An issued invoice takes payments (cash, transfer
 * or a Paystack link) and refund requests; an admin decides refunds elsewhere.
 */
export function InvoiceDetail({ invoiceId, canWrite }: { invoiceId: string; canWrite: boolean }) {
  const key = ["invoice", invoiceId];
  const invoice = useQuery({ queryKey: key, queryFn: () => getInvoice(invoiceId) });

  if (invoice.isPending) return <p>Loading...</p>;
  if (invoice.isError) {
    return (
      <p role="alert" className="error">
        {errorMessage(invoice.error)}
      </p>
    );
  }
  const data = invoice.data;
  const isDraft = data.status === "draft";
  const isIssued = data.status === "issued";

  return (
    <section className="grid gap-6">
      <Link href="/billing" className="text-sm text-accent print:hidden">
        ← Billing
      </Link>
      <Header invoice={data} />
      <Lines invoice={data} editable={isDraft && canWrite} />
      {isDraft && canWrite && <DraftActions invoice={data} />}
      {data.status === "void" && (
        <p className="notice">This draft was voided: {data.void_reason}</p>
      )}
      {isIssued && <Payments invoice={data} canWrite={canWrite} />}
      {isIssued && canWrite && data.balance_kobo > 0 && (
        <div className="grid gap-6 md:grid-cols-2">
          <TakePayment invoice={data} />
          <PaymentLinks invoice={data} />
        </div>
      )}
      {isIssued && !(canWrite && data.balance_kobo > 0) && data.online_payments.length > 0 && (
        <PaymentLinks invoice={data} readOnly={!canWrite} />
      )}
      {data.refunds.length > 0 && <Refunds invoice={data} />}
    </section>
  );
}

function Header({ invoice }: { invoice: Invoice }) {
  return (
    <div className="card">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mb-0">
          {invoice.number ? `Invoice ${invoice.number}` : "Draft invoice"}
        </h1>
        <span className="badge bg-gray-200 text-gray-800">
          {label(INVOICE_STATUS_LABELS, invoice.status)}
        </span>
        <span className={`badge ${PAYMENT_STATUS_STYLES[invoice.payment_status] ?? ""}`}>
          {label(PAYMENT_STATUS_LABELS, invoice.payment_status)}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-5">
        <Amount term="Total" kobo={invoice.total_kobo} />
        <Amount term="Paid" kobo={invoice.paid_kobo} />
        <Amount term="Refunded" kobo={invoice.refunded_kobo} />
        <Amount term="Still owed" kobo={invoice.balance_kobo} strong />
        {invoice.credit_kobo > 0 && <Amount term="To give back" kobo={invoice.credit_kobo} strong />}
      </dl>
      {invoice.issued_at && (
        <p className="m-0 text-sm">Issued {formatDateTime(invoice.issued_at)}</p>
      )}
    </div>
  );
}

function Amount({ term, kobo, strong = false }: { term: string; kobo: number; strong?: boolean }) {
  return (
    <div>
      <dt className="text-sm">{term}</dt>
      <dd className={`m-0 font-mono ${strong ? "text-lg font-bold" : ""}`}>{formatNaira(kobo)}</dd>
    </div>
  );
}

function useRefresh(invoiceId: string) {
  const queryClient = useQueryClient();
  return (fresh?: Invoice) => {
    if (fresh) queryClient.setQueryData(["invoice", invoiceId], fresh);
    void queryClient.invalidateQueries({ queryKey: ["invoice", invoiceId] });
  };
}

function Lines({ invoice, editable }: { invoice: Invoice; editable: boolean }) {
  const refresh = useRefresh(invoice.id);
  const remove = useMutation({
    mutationFn: (lineId: string) => removeInvoiceLine(invoice.id, lineId),
    onSuccess: refresh,
  });

  return (
    <section aria-labelledby="lines-heading" className="card">
      <h2 id="lines-heading" className="mb-0">
        Services
      </h2>
      {invoice.lines.length === 0 && <p>No services yet.</p>}
      {invoice.lines.length > 0 && (
        <table className="w-full text-left">
          <thead>
            <tr className="text-sm">
              <th scope="col">Service</th>
              <th scope="col" className="text-right">
                Price
              </th>
              <th scope="col" className="text-right">
                How many
              </th>
              <th scope="col" className="text-right">
                Amount
              </th>
              {editable && <th scope="col" className="sr-only">Remove</th>}
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((line) => (
              <tr key={line.id} className="border-t border-line">
                <td className="py-2">{line.description}</td>
                <td className="text-right font-mono">{formatNaira(line.unit_price_kobo)}</td>
                <td className="text-right">{line.quantity}</td>
                <td className="text-right font-mono">{formatNaira(line.amount_kobo)}</td>
                {editable && (
                  <td className="text-right">
                    <ConfirmAction
                      label="Remove"
                      question="Take this service off?"
                      pending={remove.isPending}
                      onConfirm={() => remove.mutate(line.id)}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {remove.isError && (
        <p role="alert" className="error">
          {errorMessage(remove.error)}
        </p>
      )}
    </section>
  );
}

function DraftActions({ invoice }: { invoice: Invoice }) {
  const refresh = useRefresh(invoice.id);
  const prices = useQuery({ queryKey: ["prices", false], queryFn: () => getPrices(false) });
  const [priceId, setPriceId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState("");
  const add = useMutation({
    mutationFn: () => addInvoiceLine(invoice.id, priceId || prices.data?.[0]?.id || "", quantity),
    onSuccess: (fresh) => {
      setQuantity(1);
      refresh(fresh);
    },
  });
  const issue = useMutation({ mutationFn: () => issueInvoice(invoice.id), onSuccess: refresh });
  const cancel = useMutation({
    mutationFn: () => voidInvoice(invoice.id, reason),
    onSuccess: refresh,
  });

  function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    add.mutate();
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <form className="card" onSubmit={handleAdd} noValidate aria-labelledby="add-line-heading">
        <h2 id="add-line-heading" className="mb-0">
          Add a service
        </h2>
        {prices.data?.length === 0 && (
          <p>The price list is empty. An admin adds services under Prices.</p>
        )}
        <div className="field">
          <label htmlFor="line-service">Service</label>
          <select
            id="line-service"
            value={priceId || prices.data?.[0]?.id || ""}
            onChange={(event) => setPriceId(event.target.value)}
          >
            {prices.data?.map((price) => (
              <option key={price.id} value={price.id}>
                {price.name} · {formatNaira(price.price_kobo)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="line-quantity">How many</label>
          <input
            id="line-quantity"
            type="number"
            min={1}
            max={100}
            value={quantity}
            onChange={(event) => setQuantity(Math.trunc(Number(event.target.value)) || 1)}
          />
        </div>
        {add.isError && (
          <p role="alert" className="error">
            {errorMessage(add.error)}
          </p>
        )}
        <div>
          <button className="button" type="submit" disabled={add.isPending || !prices.data?.length}>
            Add
          </button>
        </div>
      </form>

      <div className="card">
        <h2 className="mb-0">Finish</h2>
        <p className="m-0 text-sm">
          Issuing gives the invoice its number and freezes it. After that, only payments and
          refunds change what is owed.
        </p>
        <ConfirmAction
          label="Issue invoice"
          question={`Issue it for ${formatNaira(invoice.total_kobo)}?`}
          pending={issue.isPending || invoice.lines.length === 0}
          onConfirm={() => issue.mutate()}
          quiet={false}
        />
        {issue.isError && (
          <p role="alert" className="error">
            {errorMessage(issue.error)}
          </p>
        )}
        <div className="field">
          <label htmlFor="void-reason">Made by mistake? Say why, then void it</label>
          <input id="void-reason" value={reason} onChange={(event) => setReason(event.target.value)} />
        </div>
        <ConfirmAction
          label="Void this draft"
          question="Void this draft? The visit can then be billed again."
          pending={cancel.isPending || reason.trim().length < 3}
          onConfirm={() => cancel.mutate()}
        />
        {cancel.isError && (
          <p role="alert" className="error">
            {errorMessage(cancel.error)}
          </p>
        )}
      </div>
    </div>
  );
}

function Payments({ invoice, canWrite }: { invoice: Invoice; canWrite: boolean }) {
  return (
    <section aria-labelledby="payments-heading" className="card">
      <h2 id="payments-heading" className="mb-0">
        Payments
      </h2>
      {invoice.payments.length === 0 && <p>Nothing paid yet.</p>}
      <ul className="grid gap-2">
        {invoice.payments.map((payment) => (
          <li key={payment.id} className="grid gap-2 border-t border-line pt-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-mono">{payment.receipt_number}</span>
              <span>{label(METHOD_LABELS, payment.method)}</span>
              <span className="font-mono font-semibold">{formatNaira(payment.amount_kobo)}</span>
              {payment.reference && <span className="text-sm">Ref. {payment.reference}</span>}
              <span className="text-sm">{formatDateTime(payment.received_at)}</span>
              <Link
                className="button-secondary ml-auto"
                href={`/billing/receipts/${payment.id}`}
              >
                Receipt
              </Link>
            </div>
            {canWrite && <RefundAsk invoice={invoice} payment={payment} />}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Refunds({ invoice }: { invoice: Invoice }) {
  return (
    <section aria-labelledby="refunds-heading" className="card">
      <h2 id="refunds-heading" className="mb-0">
        Refunds
      </h2>
      <ul className="grid gap-2">
        {invoice.refunds.map((refund) => (
          <li
            key={refund.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2"
          >
            {refund.refund_number && <span className="font-mono">{refund.refund_number}</span>}
            <span className="font-mono font-semibold">{formatNaira(refund.amount_kobo)}</span>
            <span>{label(METHOD_LABELS, refund.method)}</span>
            <span className="badge bg-gray-200 text-gray-800">
              {label(REFUND_STATUS_LABELS, refund.status)}
            </span>
            <span className="text-sm">{refund.reason}</span>
            {refund.decision_note && (
              <span className="text-sm">Admin: {refund.decision_note}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
