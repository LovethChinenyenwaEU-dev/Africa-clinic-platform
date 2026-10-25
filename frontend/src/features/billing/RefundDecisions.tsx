"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { getStaff } from "@/features/audit/api";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import { approveRefund, getRefunds, rejectRefund } from "./api";
import { METHOD_LABELS, REFUND_STATUS_LABELS, label } from "./labels";
import { formatNaira } from "./money";
import type { Refund } from "./schemas";

type Status = "requested" | "approved" | "rejected";
const TABS: { status: Status; label: string }[] = [
  { status: "requested", label: "Waiting" },
  { status: "approved", label: "Approved" },
  { status: "rejected", label: "Rejected" },
];

/*
 * Admins decide the refunds front desk and billing ask for (FR-B3). Nobody decides a
 * refund they asked for themselves; the server refuses it too.
 */
export function RefundDecisions({ meId }: { meId: string }) {
  const [status, setStatus] = useState<Status>("requested");
  const refunds = useQuery({ queryKey: ["refunds", status], queryFn: () => getRefunds(status) });
  const staff = useQuery({ queryKey: ["staff"], queryFn: getStaff });
  const nameOf = (id: string | null) =>
    (id && staff.data?.find((person) => person.id === id)?.full_name) || "(name not found)";

  return (
    <section className="grid gap-6">
      <div>
        <h1 className="mb-1">Refunds</h1>
        <p className="text-sm">
          Front desk and billing ask; you decide. An approved refund gets its number and the
          money goes back. Say why when you reject one.
        </p>
      </div>
      <div role="group" aria-label="Show" className="flex gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.status}
            type="button"
            className={tab.status === status ? "button" : "button-secondary"}
            aria-pressed={tab.status === status}
            onClick={() => setStatus(tab.status)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <section className="card" aria-live="polite">
        {refunds.isPending && <p>Loading...</p>}
        {refunds.isError && (
          <p role="alert" className="error">
            {errorMessage(refunds.error)}
          </p>
        )}
        {refunds.data?.length === 0 && (
          <p>{status === "requested" ? "No refunds waiting." : "None yet."}</p>
        )}
        <ul className="grid gap-3">
          {refunds.data?.map((refund) => (
            <RefundRow key={refund.id} refund={refund} meId={meId} nameOf={nameOf} />
          ))}
        </ul>
      </section>
    </section>
  );
}

function RefundRow({
  refund,
  meId,
  nameOf,
}: {
  refund: Refund;
  meId: string;
  nameOf: (id: string | null) => string;
}) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["refunds"] });
  const approve = useMutation({ mutationFn: () => approveRefund(refund.id, note), onSuccess: refresh });
  const reject = useMutation({ mutationFn: () => rejectRefund(refund.id, note), onSuccess: refresh });
  const waiting = refund.status === "requested";
  const mine = refund.requested_by_id === meId;
  const noteId = `refund-note-${refund.id}`;

  return (
    <li className="grid gap-2 border-t border-line pt-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-lg font-bold">{formatNaira(refund.amount_kobo)}</span>
        <span>{label(METHOD_LABELS, refund.method)}</span>
        {refund.refund_number && <span className="font-mono">{refund.refund_number}</span>}
        <span className="badge bg-gray-200 text-gray-800">
          {label(REFUND_STATUS_LABELS, refund.status)}
        </span>
        <Link className="ml-auto text-sm text-accent" href={`/billing/invoices/${refund.invoice_id}`}>
          Open the invoice
        </Link>
      </div>
      <p className="m-0">
        <span className="font-semibold">Why:</span> {refund.reason}
      </p>
      <p className="m-0 text-sm">
        Asked by {nameOf(refund.requested_by_id)}, {formatDateTime(refund.requested_at)}
        {refund.decided_at &&
          ` · decided by ${nameOf(refund.decided_by_id)}, ${formatDateTime(refund.decided_at)}`}
      </p>
      {refund.decision_note && <p className="m-0 text-sm">Note: {refund.decision_note}</p>}
      {waiting && mine && (
        <p className="notice m-0">You asked for this one, so another admin must decide it.</p>
      )}
      {waiting && !mine && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="field grow">
            <label htmlFor={noteId}>Note (needed to reject)</label>
            <input id={noteId} value={note} onChange={(event) => setNote(event.target.value)} />
          </div>
          <ConfirmAction
            label="Approve"
            question={`Give back ${formatNaira(refund.amount_kobo)}?`}
            pending={approve.isPending || reject.isPending}
            onConfirm={() => approve.mutate()}
            quiet={false}
          />
          <ConfirmAction
            label="Reject"
            question="Reject this refund?"
            pending={approve.isPending || reject.isPending || note.trim().length < 3}
            onConfirm={() => reject.mutate()}
          />
        </div>
      )}
      {(approve.isError || reject.isError) && (
        <p role="alert" className="error">
          {errorMessage(approve.error ?? reject.error)}
        </p>
      )}
    </li>
  );
}
