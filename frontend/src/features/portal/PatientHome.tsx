"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { Logo } from "@/components/brand/Logo";
import { STATUS_LABELS, VISIT_TYPE_LABELS } from "@/features/scheduling/labels";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { forgetSavedPages } from "@/lib/sync/service-worker";

import { getMe, getMySummaries, getMyVisits, signOutPatient, splitVisits, type MyVisit } from "./api";
import { PatientRemoteCare } from "./PatientRemoteCare";
import { PatientRemoteVisit } from "./PatientRemoteVisit";

function VisitLine({ visit }: { visit: MyVisit }) {
  return (
    <li className="grid gap-1 border-t border-line pt-2">
      <span className="font-semibold">{formatDateTime(visit.starts_at)}</span>
      <span className="text-sm">
        {VISIT_TYPE_LABELS[visit.visit_type] ?? visit.visit_type}
        {visit.clinician_name ? ` with ${visit.clinician_name}` : ""} ·{" "}
        {STATUS_LABELS[visit.status] ?? visit.status}
      </span>
    </li>
  );
}

/*
 * The patient's own page: their visits, and the summaries their clinician approved.
 * Nothing here is ever kept on the device for offline use.
 */
export function PatientHome({ clinicId }: { clinicId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["portal", "me"], queryFn: getMe });
  const visits = useQuery({ queryKey: ["portal", "visits"], queryFn: getMyVisits });
  const summaries = useQuery({ queryKey: ["portal", "summaries"], queryFn: getMySummaries });
  const signOut = useMutation({
    mutationFn: async () => {
      await signOutPatient();
      await forgetSavedPages().catch(() => {});
    },
    onSuccess: () => {
      queryClient.clear();
      router.replace(`/patient/${clinicId}`);
    },
  });

  const { upcoming, past } = splitVisits(visits.data ?? []);

  return (
    <main className="mx-auto grid max-w-2xl gap-5 px-4 py-6">
      <Logo size="sm" tagline />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="mb-0">{me.data ? `Hello, ${me.data.full_name}` : "Your clinic record"}</h1>
        <button
          className="button-secondary"
          type="button"
          disabled={signOut.isPending}
          onClick={() => signOut.mutate()}
        >
          Sign out
        </button>
      </div>

      <section aria-labelledby="my-visits" className="card grid gap-2">
        <h2 id="my-visits" className="mb-0">
          Your visits
        </h2>
        {visits.isPending && <p>Loading...</p>}
        {visits.isError && <p className="error">{errorMessage(visits.error)}</p>}
        {visits.data && upcoming.length === 0 && <p>No visits booked.</p>}
        {upcoming.length > 0 && (
          <ul className="grid gap-2">
            {upcoming.map((visit) => (
              <VisitLine key={visit.appointment_id} visit={visit} />
            ))}
          </ul>
        )}
        {past.length > 0 && (
          <details>
            <summary className="text-sm">Earlier visits ({past.length})</summary>
            <ul className="grid gap-2 pt-2">
              {past.map((visit) => (
                <VisitLine key={visit.appointment_id} visit={visit} />
              ))}
            </ul>
          </details>
        )}
      </section>

      {upcoming.map((visit) => (
        <PatientRemoteVisit key={visit.appointment_id} visit={visit} />
      ))}

      {visits.data && (
        <PatientRemoteCare
          hasRemoteVisit={upcoming.some(
            (visit) => visit.visit_type === "teleconsult" && visit.status !== "cancelled",
          )}
        />
      )}

      <section aria-labelledby="my-summaries" className="card grid gap-3">
        <h2 id="my-summaries" className="mb-0">
          Visit summaries from your clinician
        </h2>
        {summaries.isPending && <p>Loading...</p>}
        {summaries.isError && <p className="error">{errorMessage(summaries.error)}</p>}
        {summaries.data?.length === 0 && (
          <p>No summaries yet. Your clinician approves one after each visit.</p>
        )}
        {summaries.data?.map((summary) => (
          <article key={summary.id} className="grid gap-1 border-t border-line pt-2">
            {summary.approved_at && (
              <p className="text-sm">Approved {formatDateTime(summary.approved_at)}</p>
            )}
            <p className="whitespace-pre-wrap">{summary.body}</p>
          </article>
        ))}
      </section>

      <p className="text-sm">
        Feeling much worse, or have difficulty breathing, chest pain, confusion, fits or heavy
        bleeding? Do not wait: go to the clinic or the nearest emergency department now.
      </p>
    </main>
  );
}
