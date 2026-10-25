"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PatientPicker } from "@/features/patients/PatientPicker";
import type { Patient } from "@/features/patients/schemas";
import { STATUS_LABELS } from "@/features/scheduling/labels";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import { getVisitsToBill, startInvoice } from "./api";
import {
  INVOICE_STATUS_LABELS,
  PAYMENT_STATUS_LABELS,
  PAYMENT_STATUS_STYLES,
  label,
} from "./labels";
import { formatNaira } from "./money";
import type { VisitToBill } from "./schemas";

/*
 * The front desk's and billing's start point: find the patient, see their recent
 * visits, and bill one. Each visit has at most one live invoice.
 */
export function BillingDesk() {
  const [patient, setPatient] = useState<Patient | null>(null);

  return (
    <section className="grid gap-6">
      <div>
        <h1 className="mb-1">Billing</h1>
        <p className="text-sm">
          Find the patient, then bill a visit from the price list. Payments, receipts and
          payment links are on the invoice.
        </p>
      </div>
      <div className="card">
        <h2 className="mb-0">Patient</h2>
        <PatientPicker chosen={patient} onChoose={setPatient} />
      </div>
      {patient && <Visits patientId={patient.id} />}
    </section>
  );
}

function Visits({ patientId }: { patientId: string }) {
  const visits = useQuery({
    queryKey: ["visits-to-bill", patientId],
    queryFn: () => getVisitsToBill(patientId),
  });

  return (
    <section aria-labelledby="visits-heading" className="card">
      <h2 id="visits-heading" className="mb-0">
        Recent visits
      </h2>
      {visits.isPending && <p>Loading...</p>}
      {visits.isError && (
        <p role="alert" className="error">
          {errorMessage(visits.error)}
        </p>
      )}
      {visits.data?.length === 0 && <p>No visits yet. Book or register one first.</p>}
      {visits.data && visits.data.length > 0 && (
        <ul className="grid gap-2">
          {visits.data.map((visit) => (
            <VisitRow key={visit.appointment_id} visit={visit} />
          ))}
        </ul>
      )}
    </section>
  );
}

function VisitRow({ visit }: { visit: VisitToBill }) {
  const router = useRouter();
  const start = useMutation({
    mutationFn: () => startInvoice(visit.appointment_id),
    onSuccess: (invoice) => router.push(`/billing/invoices/${invoice.id}`),
  });
  const invoice = visit.invoice;

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2">
      <span className="font-semibold">{formatDateTime(visit.starts_at)}</span>
      <span className="text-sm">
        {visit.visit_type === "teleconsult" ? "Remote" : "In person"} ·{" "}
        {label(STATUS_LABELS, visit.status)}
      </span>
      {invoice ? (
        <>
          <span className="font-mono">
            {invoice.number ?? label(INVOICE_STATUS_LABELS, invoice.status)}
          </span>
          <span className={`badge ${PAYMENT_STATUS_STYLES[invoice.payment_status] ?? ""}`}>
            {label(PAYMENT_STATUS_LABELS, invoice.payment_status)}
          </span>
          {invoice.balance_kobo > 0 && (
            <span className="text-sm">Owes {formatNaira(invoice.balance_kobo)}</span>
          )}
          <Link className="button-secondary ml-auto" href={`/billing/invoices/${invoice.id}`}>
            Open invoice
          </Link>
        </>
      ) : (
        <button
          type="button"
          className="button ml-auto"
          disabled={start.isPending}
          onClick={() => start.mutate()}
        >
          {start.isPending ? "Starting..." : "Bill this visit"}
        </button>
      )}
      {start.isError && (
        <p role="alert" className="error w-full">
          {errorMessage(start.error)}
        </p>
      )}
    </li>
  );
}
