"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { getPatient } from "@/features/patients/api";
import { SEX_LABELS } from "@/features/patients/labels";
import { getClinicians } from "@/features/scheduling/api";
import { errorMessage } from "@/lib/api-client";
import { ageFrom, formatDate, formatDateTime } from "@/lib/format";

import { getEncounter, markOpenedByMistake, signOff, type SignOffResult } from "./api";
import { AllergiesPanel, ProblemsPanel } from "./ChartPanels";
import { ENCOUNTER_STATUS_LABELS } from "./labels";
import { NotesPanel } from "./NotesPanel";
import { VitalsPanel } from "./VitalsPanel";

export function EncounterScreen({ encounterId, meId }: { encounterId: string; meId: string }) {
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

  if (encounter.isPending) return <p>Loading the encounter...</p>;
  if (encounter.isError) {
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

  const record = encounter.data;
  const nameOf = (staffId: string) =>
    staffId === meId
      ? "you"
      : (clinicians.data?.find((person) => person.id === staffId)?.full_name ?? "a clinician");
  const isOwner = record.clinician_id === meId;
  const isOpen = record.status === "open";
  const context = { encounter: record, meId, nameOf };

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

        {isOpen && isOwner && (
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

      <AllergiesPanel {...context} />
      <VitalsPanel {...context} />
      <ProblemsPanel {...context} />
      <NotesPanel {...context} />
    </div>
  );
}
