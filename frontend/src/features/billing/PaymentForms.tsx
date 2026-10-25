"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import { checkPaymentLink, recordPayment, requestRefund, sendPaymentLink } from "./api";
import { LINK_STATUS_LABELS, label } from "./labels";
import { formatNaira, nairaInput, parseNaira } from "./money";
import type { Invoice, Payment } from "./schemas";

const AMOUNT_HINT = "Type the amount in naira, for example 5000 or 5,000.50.";

function useInvoiceRefresh(invoiceId: string) {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: ["invoice", invoiceId] });
}

/** Cash, or a bank transfer the clinic has seen arrive. Never more than is owed. */
export function TakePayment({ invoice }: { invoice: Invoice }) {
  const refresh = useInvoiceRefresh(invoice.id);
  const [method, setMethod] = useState<"cash" | "transfer">("cash");
  const [amount, setAmount] = useState(nairaInput(invoice.balance_kobo));
  const [reference, setReference] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const take = useMutation({
    mutationFn: (kobo: number) =>
      recordPayment(invoice.id, { method, amount_kobo: kobo, reference }),
    onSuccess: () => {
      setReference("");
      refresh();
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const kobo = parseNaira(amount);
    if (kobo === null || kobo === 0) return setProblem(AMOUNT_HINT);
    if (kobo > invoice.balance_kobo) {
      return setProblem(`That is more than the ${formatNaira(invoice.balance_kobo)} still owed.`);
    }
    if (method === "transfer" && reference.trim().length < 3) {
      return setProblem("A transfer needs the bank's reference.");
    }
    setProblem(null);
    take.mutate(kobo);
  }

  return (
    <form className="card" onSubmit={handleSubmit} noValidate aria-labelledby="take-heading">
      <h2 id="take-heading" className="mb-0">
        Take a payment
      </h2>
      <fieldset className="flex gap-4 border-0 p-0">
        <legend className="mb-1 font-semibold">How</legend>
        {(["cash", "transfer"] as const).map((choice) => (
          <label key={choice} className="flex items-center gap-2 font-normal">
            <input
              type="radio"
              name="method"
              value={choice}
              checked={method === choice}
              onChange={() => setMethod(choice)}
            />
            {choice === "cash" ? "Cash" : "Bank transfer"}
          </label>
        ))}
      </fieldset>
      <div className="field">
        <label htmlFor="pay-amount">Amount (₦)</label>
        <input
          id="pay-amount"
          inputMode="decimal"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="pay-reference">
          {method === "transfer" ? "Bank reference" : "Note (optional)"}
        </label>
        <input
          id="pay-reference"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
        />
      </div>
      {(problem || take.isError) && (
        <p role="alert" className="error">
          {problem ?? errorMessage(take.error)}
        </p>
      )}
      {take.isSuccess && (
        <p role="status" className="m-0 text-sm">
          Recorded: receipt {take.data.receipt_number}.
        </p>
      )}
      <div>
        <button className="button" type="submit" disabled={take.isPending}>
          {take.isPending ? "Recording..." : "Record payment"}
        </button>
      </div>
    </form>
  );
}

/** Paystack links: make one for what is owed, and check the ones already sent. */
export function PaymentLinks({ invoice, readOnly = false }: { invoice: Invoice; readOnly?: boolean }) {
  const refresh = useInvoiceRefresh(invoice.id);
  const [email, setEmail] = useState("");
  const send = useMutation({
    mutationFn: () => sendPaymentLink(invoice.id, { email }),
    onSuccess: refresh,
  });
  const check = useMutation({ mutationFn: checkPaymentLink, onSuccess: refresh });
  const canSend = !readOnly && invoice.balance_kobo > 0;

  return (
    <section aria-labelledby="links-heading" className="card">
      <h2 id="links-heading" className="mb-0">
        Pay online
      </h2>
      {canSend && (
        <>
          <p className="m-0 text-sm">
            A Paystack link for the {formatNaira(invoice.balance_kobo)} still owed. Send it to
            the patient by SMS or WhatsApp. It counts once Paystack confirms the payment.
          </p>
          <div className="field">
            <label htmlFor="link-email">Patient&apos;s email (optional)</label>
            <input
              id="link-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div>
            <button
              type="button"
              className="button"
              disabled={send.isPending}
              onClick={() => send.mutate()}
            >
              {send.isPending ? "Making the link..." : "Make a payment link"}
            </button>
          </div>
          {send.isError && (
            <p role="alert" className="error">
              {errorMessage(send.error)}
            </p>
          )}
        </>
      )}
      {invoice.online_payments.length > 0 && (
        <ul className="grid gap-2">
          {invoice.online_payments.map((row) => (
            <li key={row.id} className="grid gap-1 border-t border-line pt-2">
              <span className="flex flex-wrap items-center gap-x-3">
                <span className="font-mono font-semibold">{formatNaira(row.amount_kobo)}</span>
                <span className="badge bg-gray-200 text-gray-800">
                  {label(LINK_STATUS_LABELS, row.status)}
                </span>
                <span className="text-sm">{formatDateTime(row.created_at)}</span>
                {!readOnly && row.status === "pending" && (
                  <button
                    type="button"
                    className="button-secondary ml-auto"
                    disabled={check.isPending}
                    onClick={() => check.mutate(row.id)}
                  >
                    Check now
                  </button>
                )}
              </span>
              {row.status === "pending" && (
                <a className="break-all text-sm text-accent" href={row.link} target="_blank" rel="noreferrer">
                  {row.link}
                </a>
              )}
              {row.failure_reason && <span className="text-sm">{row.failure_reason}</span>}
            </li>
          ))}
        </ul>
      )}
      {check.isError && (
        <p role="alert" className="error">
          {errorMessage(check.error)}
        </p>
      )}
    </section>
  );
}

/** Ask for money back from one payment. An admin who did not ask decides. */
export function RefundAsk({ invoice, payment }: { invoice: Invoice; payment: Payment }) {
  const refresh = useInvoiceRefresh(invoice.id);
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(nairaInput(payment.amount_kobo));
  const [method, setMethod] = useState<"cash" | "transfer">("cash");
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const ask = useMutation({
    mutationFn: (kobo: number) => requestRefund(payment.id, { amount_kobo: kobo, method, reason }),
    onSuccess: () => {
      setOpen(false);
      setReason("");
      refresh();
    },
  });

  if (!open) {
    return (
      <div>
        <button type="button" className="button-secondary" onClick={() => setOpen(true)}>
          Ask for a refund
        </button>
        {ask.isSuccess && (
          <span role="status" className="ml-3 text-sm">
            Asked. An admin will decide.
          </span>
        )}
      </div>
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const kobo = parseNaira(amount);
    if (kobo === null || kobo === 0) return setProblem(AMOUNT_HINT);
    if (kobo > payment.amount_kobo) return setProblem("That is more than this payment.");
    if (reason.trim().length < 3) return setProblem("Say why the money goes back.");
    setProblem(null);
    ask.mutate(kobo);
  }

  const idFor = (name: string) => `refund-${name}-${payment.id}`;
  return (
    <form className="grid gap-2 rounded-md bg-canvas p-3 sm:grid-cols-3" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor={idFor("amount")}>Amount (₦)</label>
        <input
          id={idFor("amount")}
          inputMode="decimal"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={idFor("method")}>Give back as</label>
        <select
          id={idFor("method")}
          value={method}
          onChange={(event) => setMethod(event.target.value === "transfer" ? "transfer" : "cash")}
        >
          <option value="cash">Cash</option>
          <option value="transfer">Bank transfer</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor={idFor("reason")}>Why</label>
        <input id={idFor("reason")} value={reason} onChange={(event) => setReason(event.target.value)} />
      </div>
      {(problem || ask.isError) && (
        <p role="alert" className="error sm:col-span-3">
          {problem ?? errorMessage(ask.error)}
        </p>
      )}
      <div className="flex gap-2 sm:col-span-3">
        <button className="button" type="submit" disabled={ask.isPending}>
          Ask an admin
        </button>
        <button type="button" className="button-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
