"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime, todayInLagos } from "@/lib/format";

import {
  agreeToRemoteCare,
  bookRemoteVisit,
  getRemoteCareConsent,
  getRemoteSlots,
  type RemoteSlot,
} from "./api";

const SLOTS_SHOWN = 12;

/*
 * Booking a remote consultation on the patient page: read and agree to the clinic's
 * wording for remote care, then pick a free slot. The intake comes next, on the visit.
 */
export function PatientRemoteCare({ hasRemoteVisit }: { hasRemoteVisit: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const consent = useQuery({ queryKey: ["portal", "consent"], queryFn: getRemoteCareConsent });
  const slots = useQuery({
    queryKey: ["portal", "slots"],
    queryFn: () => getRemoteSlots(todayInLagos()),
    enabled: open && consent.data?.consented === true,
  });
  const agree = useMutation({
    mutationFn: agreeToRemoteCare,
    onSuccess: (state) => queryClient.setQueryData(["portal", "consent"], state),
  });
  const book = useMutation({
    mutationFn: (slot: RemoteSlot) => bookRemoteVisit(slot),
    onSuccess: () => {
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["portal"] });
    },
  });

  if (hasRemoteVisit) return null; // one remote visit booked here at a time

  return (
    <section aria-labelledby="remote-care" className="card grid gap-3">
      <h2 id="remote-care" className="mb-0">
        Talk to a clinician from home
      </h2>
      {!open ? (
        <div>
          <p className="text-sm">
            A video, phone-quality audio or text consultation. Not for emergencies.
          </p>
          <button className="button" type="button" onClick={() => setOpen(true)}>
            Book a remote consultation
          </button>
        </div>
      ) : (
        <div className="grid gap-3">
          {consent.isPending && <p>Loading...</p>}
          {consent.isError && <p className="error">{errorMessage(consent.error)}</p>}
          {consent.data && !consent.data.wording && (
            <p className="notice">
              This clinic does not offer remote consultations online yet. Please call the
              clinic.
            </p>
          )}
          {consent.data?.wording && !consent.data.consented && (
            <div className="grid gap-2">
              <p className="font-semibold">Before your first remote consultation, please read:</p>
              <p className="whitespace-pre-wrap rounded border border-line p-3">
                {consent.data.wording}
              </p>
              <button
                className="button"
                type="button"
                disabled={agree.isPending}
                onClick={() => agree.mutate()}
              >
                {agree.isPending ? "Saving..." : "I have read this and I agree"}
              </button>
              {agree.isError && <p className="error">{errorMessage(agree.error)}</p>}
            </div>
          )}
          {consent.data?.consented && (
            <div className="grid gap-2">
              <p className="font-semibold">Choose a time (Lagos time)</p>
              {slots.isPending && <p>Loading free times...</p>}
              {slots.isError && <p className="error">{errorMessage(slots.error)}</p>}
              {slots.data?.length === 0 && (
                <p>No free remote times this week. Please try again tomorrow, or call the clinic.</p>
              )}
              <ul className="grid gap-2">
                {slots.data?.slice(0, SLOTS_SHOWN).map((slot) => (
                  <li
                    key={`${slot.clinician_id}-${slot.starts_at}`}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1"
                  >
                    <span className="font-semibold">{formatDateTime(slot.starts_at)}</span>
                    <span className="text-sm">with {slot.clinician_name}</span>
                    <span className="ml-auto">
                      <ConfirmAction
                        label="Book"
                        question={`Book ${formatDateTime(slot.starts_at)}?`}
                        quiet={false}
                        pending={book.isPending}
                        onConfirm={() => book.mutate(slot)}
                      />
                    </span>
                  </li>
                ))}
              </ul>
              {book.isError && (
                <p role="alert" className="error">
                  {errorMessage(book.error)}
                </p>
              )}
            </div>
          )}
          <div>
            <button className="button-secondary" type="button" onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
