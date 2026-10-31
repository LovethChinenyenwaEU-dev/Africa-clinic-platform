"use client";

import { useMutation } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";

import { downloadText } from "@/features/billing/download";
import { errorMessage } from "@/lib/api-client";
import { todayInLagos } from "@/lib/format";

import { REASONS, countResources, exportFileName, exportRecord, type ExportReason } from "./api";

/*
 * "Download record (FHIR)" on the patient page, for doctors and nurses (Week 11).
 * The person says why; the backend checks consent for sharing and writes the reason in
 * the audit log. The file holds the whole record, so the page says to handle it with care.
 */
export function RecordExport({ patientId }: { patientId: string }) {
  const [reason, setReason] = useState<ExportReason>("patient_request");
  const download = useMutation({
    mutationFn: () => exportRecord(patientId, reason),
    onSuccess: (bundle) =>
      downloadText(
        exportFileName(patientId, todayInLagos()),
        JSON.stringify(bundle, null, 2),
        "application/fhir+json",
      ),
  });
  const counts = download.data ? countResources(download.data) : null;

  return (
    <section className="card gap-3">
      <div>
        <h2 className="mb-1 text-base">Export the record (FHIR)</h2>
        <p className="m-0 text-sm">
          A file in the HL7 FHIR standard that another clinic&apos;s system can read: visits,
          vital signs, allergies, diagnoses, medicines and consents. Clinical notes are not
          included.
        </p>
      </div>
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-semibold">Why are you exporting it?</legend>
        {REASONS.map((option) => (
          <label key={option.value} className="flex items-start gap-2">
            <input
              type="radio"
              name="export-reason"
              value={option.value}
              checked={reason === option.value}
              onChange={() => {
                setReason(option.value);
                download.reset();
              }}
              className="mt-1"
            />
            <span>
              {option.label}
              <span className="block text-sm">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <div>
        <button
          type="button"
          className="button inline-flex items-center gap-2"
          disabled={download.isPending}
          onClick={() => download.mutate()}
        >
          <Download aria-hidden className="size-4" />
          {download.isPending ? "Preparing..." : "Download record (FHIR)"}
        </button>
      </div>
      <p className="m-0 text-sm">
        The reason is written in the audit log. The file holds the whole record: send it only
        by a secure route, and delete it from this device afterwards.
      </p>
      {download.isError && (
        <p role="alert" className="error">
          {errorMessage(download.error)}
        </p>
      )}
      {counts && (
        <p role="status" className="m-0 text-sm">
          Downloaded: {Object.entries(counts)
            .map(([kind, count]) => `${count} ${kind}`)
            .join(", ")}
          .
        </p>
      )}
    </section>
  );
}
