"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { getPatient } from "@/features/patients/api";
import { SEX_LABELS } from "@/features/patients/labels";
import { getClinicians } from "@/features/scheduling/api";
import { OutboxList } from "@/features/sync/OutboxList";
import { useSync } from "@/features/sync/SyncProvider";
import { errorMessage } from "@/lib/api-client";
import { ageFrom, formatDate, formatDateTime } from "@/lib/format";

import { getEncounter, markOpenedByMistake, signOff, type SignOffResult } from "./api";
import { AllergiesPanel, ProblemsPanel } from "./ChartPanels";
import { ENCOUNTER_STATUS_LABELS } from "./labels";
import { NotesPanel } from "./NotesPanel";
import { VitalsPanel } from "./VitalsPanel";

export function EncounterScreen({ encounterId, meId }: { encounterId: string; meId: string }) {
  const sync = useSync();
  const queryClient = useQueryClient();
  const [signedOff, setSignedOff] = useState<SignOffResult | null>(null);

  const encounter = useQuery({
    queryKey: ["encounter", encounterId],
    queryFn: () => getEncounter(encounterId),
  });
  const patientId = encounter.data?.patient_id;
  const patient = useQuery({
    queryKey: ["patient", patientId],
    queryFn: () => getPatient(patientId ?? ""),
    enabled: Boolean(patientId),
  });
  const clinicians = useQuery({ queryKey: ["clinicians"], queryFn: getClinicians });

  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: ["encounter", encounterId] });
  const finish = useMutation({
    mutationFn: () => signOff(encounter.data!),
    onSuccess: (result) => {
      setSignedOff(result);
      refresh();
    },
  });
  const mistake = useMutation({
    mutationFn: () => markOpenedByMistake(encounterId),
    onSuccess: refresh,
  });

  if (encounter.isPending) {
    return (
      <p>
        {sync.online
          ? "Loading the encounter..."
          : "Offline, and this encounter is not saved on this device. Open it again when the network returns."}
      </p>
    );
  }
  // With a copy saved on this device, a failed refresh still shows the copy.
  if (encounter.isError && !encounter.data) {
    return (
      <section className="grid gap-3">
        <h1 className="mb-0">Could not open this encounter</h1>
        <p role="alert">{errorMessage(encounter.error)}</p>
        <Link href="/queue" className="text-accent underline">
          Back to the queue
        </Link>
      </section>
    );
  }

  const record = encounter.data!;
  const fromDevice = encounter.isError || !sync.online;
  const nameOf = (staffId: string) =>
    staffId === meId
      ? "you"
      : (clinicians.data?.find((person) => person.id === staffId)?.full_name ?? "a clinician");
  const isOwner = record.clinician_id === meId;
  const isOpen = record.status === "open";
  const context = { encounter: record, meId, nameOf };
  // Entries made here on this device and not yet on the server (or refused by it).
  const onDevice = sync.items.filter(
    (item) => item.encounterId === record.id && item.staffId === sync.staffId,
  );

  return (
    <div className="grid gap-6">
      <p>
        <Link href="/queue" className="text-accent underline">
          ← Today&apos;s queue
        </Link>
      </p>

      <section className="card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="mb-1">{patient.data?.full_name ?? "Patient"}</h1>
            {patient.data && (
              <p>
                Born {formatDate(patient.data.date_of_birth)} ({ageFrom(patient.data.date_of_birth)})
                {" · "}
                {SEX_LABELS[patient.data.sex] ?? patient.data.sex}
              </p>
            )}
            {patient.isError && <p className="error">{errorMessage(patient.error)}</p>}
          </div>
          <span
            className={`badge ${
              isOpen ? "bg-green-100 text-green-900" : "bg-gray-200 text-gray-800"
            }`}
          >
            {ENCOUNTER_STATUS_LABELS[record.status] ?? record.status}
          </span>
        </div>

        <p className="text-sm">
          Opened {formatDateTime(record.opened_at)} by {nameOf(record.clinician_id)}
          {record.closed_at &&
            record.closed_by_id &&
            ` · ${record.status === "closed" ? "signed off" : "marked as a mistake"} ${formatDateTime(
              record.closed_at,
            )} by ${nameOf(record.closed_by_id)}`}
        </p>

        {fromDevice && (
          <p role="status" className="notice">
            Showing the copy saved on this device at{" "}
            {formatDateTime(new Date(encounter.dataUpdatedAt).toISOString())}. What you add is
            kept here and sent when the network returns.
          </p>
        )}

        {signedOff && (
          <p role="status" className="notice">
            Signed off.{" "}
            {signedOff.visitCompleted
              ? "The visit is complete."
              : "The visit stays open for the clinician who started it."}
          </p>
        )}
        {record.status === "entered_in_error" && (
          <p className="notice">
            This encounter was opened by mistake. It is kept, but nothing more can be added.
          </p>
        )}

        {isOpen && isOwner && onDevice.length > 0 && (
          <p className="notice">
            Sign-off waits until the entries below have reached the server, so the record you
            sign is complete.
          </p>
        )}
        {isOpen && isOwner && onDevice.length === 0 && (
          <div className="flex flex-wrap gap-3">
            <ConfirmAction
              label="Sign off"
              question="Sign off? After this, changes are kept as new versions."
              quiet={false}
              pending={finish.isPending}
              onConfirm={() => finish.mutate()}
            />
            <ConfirmAction
              label="Opened by mistake"
              question="Mark this encounter as opened by mistake?"
              pending={mistake.isPending}
              onConfirm={() => mistake.mutate()}
            />
          </div>
        )}
        {isOpen && !isOwner && (
          <p className="text-sm">
            You can add to this record. Only {nameOf(record.clinician_id)} can sign it off.
          </p>
        )}
        {(finish.isError || mistake.isError) && (
          <p role="alert" className="error">
            {errorMessage(finish.error ?? mistake.error)}
          </p>
        )}
      </section>

      {onDevice.length > 0 && (
        <section aria-labelledby="on-device-heading" className="card">
          <h2 id="on-device-heading" className="mb-0">
            Saved on this device
          </h2>
          <p className="text-sm">
            {!onDevice.some((item) => item.status === "pending")
              ? "The server could not accept these. Read why, then dismiss them."
              : sync.online
                ? "Sending to the server..."
                : "Offline. They are kept here and sent when the network returns."}
          </p>
          <OutboxList items={onDevice} onDiscard={sync.discard} />
        </section>
      )}

      <AllergiesPanel {...context} />
      <VitalsPanel {...context} />
      <ProblemsPanel {...context} />
      <NotesPanel {...context} />
    </div>
  );
}
