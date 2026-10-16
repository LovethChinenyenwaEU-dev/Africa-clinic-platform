"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";
import { ageFrom, formatDate } from "@/lib/format";

import { decideReview, getReviewQueue } from "./api";
import { DUPLICATE_REASON_LABELS, SEX_LABELS } from "./labels";
import type { Patient, ReviewDecision } from "./schemas";

function describe(person: Patient): string {
  const born = `born ${formatDate(person.date_of_birth)} (${ageFrom(person.date_of_birth)})`;
  const phone = person.phone ? ` · ${person.phone}` : "";
  return `${born} · ${SEX_LABELS[person.sex] ?? person.sex}${phone}`;
}

/*
 * Registrations made offline that may be someone already registered. Front desk
 * compares and decides. Nothing is merged or deleted: a duplicate keeps what was
 * recorded on it and points at the original.
 */
export function ReviewQueue() {
  const queryClient = useQueryClient();
  const queue = useQuery({ queryKey: ["review-queue"], queryFn: getReviewQueue });
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: ReviewDecision }) =>
      decideReview(id, decision),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["review-queue"] }),
  });

  return (
    <section className="grid gap-6">
      <div>
        <p>
          <Link href="/patients" className="text-accent underline">
            ← Patients
          </Link>
        </p>
        <h1 className="mb-1">Registrations to review</h1>
        <p className="text-sm">
          These patients were registered with no network, and look like someone already
          registered. Compare, then decide. Nothing is deleted.
        </p>
      </div>

      {queue.isPending && <p>Loading...</p>}
      {queue.isError && (
        <p role="alert" className="error">
          {errorMessage(queue.error)}
        </p>
      )}
      {decide.isError && (
        <p role="alert" className="error">
          {errorMessage(decide.error)}
        </p>
      )}
      {queue.data?.length === 0 && <p>Nothing to review.</p>}

      {queue.data?.map(({ patient, matches }) => (
        <article key={patient.id} className="card grid gap-3">
          <div>
            <h2 className="mb-0">
              <Link href={`/patients/${patient.id}`} className="text-accent underline">
                {patient.full_name}
              </Link>
            </h2>
            <p className="text-sm">{describe(patient)} · registered offline</p>
          </div>

          <p className="font-semibold">May be the same person as:</p>
          <ul className="grid gap-2">
            {matches.map(({ patient: match, reason }) => (
              <li key={match.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <Link href={`/patients/${match.id}`} className="text-accent underline">
                  {match.full_name}
                </Link>
                <span className="text-sm">{describe(match)}</span>
                <span className="badge bg-amber-100 text-amber-900">
                  {DUPLICATE_REASON_LABELS[reason]}
                </span>
                <ConfirmAction
                  label="Same person"
                  question={`Mark as already registered as ${match.full_name}?`}
                  pending={decide.isPending}
                  onConfirm={() =>
                    decide.mutate({
                      id: patient.id,
                      decision: { decision: "duplicate", duplicate_of: match.id },
                    })
                  }
                />
              </li>
            ))}
            {matches.length === 0 && (
              <li className="text-sm">
                The possible match has changed since. Decide whether this is someone new.
              </li>
            )}
          </ul>

          <div>
            <ConfirmAction
              label="Someone new"
              question="This is a different person: keep as a new patient?"
              quiet={false}
              pending={decide.isPending}
              onConfirm={() =>
                decide.mutate({ id: patient.id, decision: { decision: "new_person" } })
              }
            />
          </div>
        </article>
      ))}
    </section>
  );
}
