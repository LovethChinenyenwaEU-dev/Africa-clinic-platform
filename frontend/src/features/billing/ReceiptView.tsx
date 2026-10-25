"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import { getReceipt } from "./api";
import { METHOD_LABELS, label } from "./labels";
import { formatNaira } from "./money";

/*
 * A receipt to print or show. The check code is made by the server with its secret,
 * so the clinic can later confirm a paper receipt is one it really gave.
 */
export function ReceiptView({ paymentId }: { paymentId: string }) {
  const receipt = useQuery({ queryKey: ["receipt", paymentId], queryFn: () => getReceipt(paymentId) });

  if (receipt.isPending) return <p>Loading...</p>;
  if (receipt.isError) {
    return (
      <p role="alert" className="error">
        {errorMessage(receipt.error)}
      </p>
    );
  }
  const r = receipt.data;

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap gap-3 print:hidden">
        <Link href={`/billing/invoices/${r.payment.invoice_id}`} className="text-sm text-accent">
          ← Invoice {r.invoice_number}
        </Link>
        <button type="button" className="button ml-auto" onClick={() => window.print()}>
          Print
        </button>
      </div>
      <article className="card mx-auto w-full max-w-md print:border-0" aria-labelledby="receipt-title">
        <header className="grid gap-1 text-center">
          <p className="m-0 font-bold">{r.clinic_name}</p>
          <h1 id="receipt-title" className="mb-0 text-xl">
            Receipt {r.payment.receipt_number}
          </h1>
          <p className="m-0 text-sm">{formatDateTime(r.payment.received_at)}</p>
        </header>
        <dl className="grid grid-cols-2 gap-y-1">
          <dt>Patient</dt>
          <dd className="m-0 text-right">{r.patient_name}</dd>
          <dt>Invoice</dt>
          <dd className="m-0 text-right font-mono">{r.invoice_number}</dd>
          <dt>Paid by</dt>
          <dd className="m-0 text-right">{label(METHOD_LABELS, r.payment.method)}</dd>
          {r.payment.reference && (
            <>
              <dt>Reference</dt>
              <dd className="m-0 text-right font-mono">{r.payment.reference}</dd>
            </>
          )}
          <dt className="font-bold">Amount</dt>
          <dd className="m-0 text-right font-mono text-lg font-bold">
            {formatNaira(r.payment.amount_kobo)}
          </dd>
          <dt>Invoice total</dt>
          <dd className="m-0 text-right font-mono">{formatNaira(r.invoice_total_kobo)}</dd>
          <dt>Paid so far</dt>
          <dd className="m-0 text-right font-mono">{formatNaira(r.paid_to_date_kobo)}</dd>
          <dt>Still owed</dt>
          <dd className="m-0 text-right font-mono">
            {formatNaira(Math.max(0, r.balance_after_kobo))}
          </dd>
          <dt>Received by</dt>
          <dd className="m-0 text-right">{r.received_by_name}</dd>
        </dl>
        <p className="m-0 border-t border-line pt-2 text-center text-sm">
          Check code <span className="font-mono font-bold">{r.check_code}</span>
        </p>
      </article>
    </section>
  );
}
