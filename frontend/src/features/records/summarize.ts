import { formatDate, todayInLagos } from "@/lib/format";

import { describePrescription } from "./prescribing";
import type { FollowUp, Prescription, Problem, Referral } from "./schemas";

/*
 * "Start from this visit": a first draft of the patient summary, in plain words, from
 * what was recorded. The clinician reads it, rewrites what a patient would not
 * understand, and only then approves it. Nothing is sent to the patient on its own.
 */

export type VisitRecord = {
  visitDay: string; // ISO moment the encounter opened
  encounterId: string;
  problems: Problem[];
  prescriptions: Prescription[];
  followUps: FollowUp[];
  referrals: Referral[];
};

const VISIT_KIND: Record<string, string> = {
  in_person: "at the clinic",
  teleconsult: "by remote consultation",
};

const URGENCY: Record<string, string> = {
  routine: "",
  urgent: " (please go within the next few days)",
  emergency: " (please go now)",
};

const SAFETY_NET =
  "If you feel worse, or notice difficulty breathing, chest pain, confusion, fits or " +
  "heavy bleeding, come to the clinic at once or go to the nearest emergency department.";

export function draftFromVisit(visit: VisitRecord): string {
  const found = visit.problems.filter(
    (row) =>
      row.encounter_id === visit.encounterId &&
      row.version_status === "current" &&
      row.clinical_status !== "entered_in_error",
  );
  const medicines = visit.prescriptions.filter(
    (row) => row.version_status === "current" && row.clinical_status === "active",
  );
  const followUps = visit.followUps.filter((row) => row.status !== "cancelled");
  const referrals = visit.referrals.filter((row) => row.status === "active");

  const day = todayInLagos(new Date(visit.visitDay)); // the Lagos calendar day of the visit
  const parts: string[] = [`Your visit on ${formatDate(day)}`];
  if (found.length > 0) {
    parts.push(["What we found:", ...found.map((row) => `- ${row.description}`)].join("\n"));
  }
  if (medicines.length > 0) {
    parts.push(
      [
        "Your medicines:",
        ...medicines.map(
          (row) => `- ${describePrescription(row)}${row.instructions ? `. ${row.instructions}` : ""}`,
        ),
      ].join("\n"),
    );
  }
  const next = [
    ...followUps.map(
      (row) =>
        `- Come back by ${formatDate(row.due_date)}, ${VISIT_KIND[row.visit_type] ?? row.visit_type}.`,
    ),
    ...referrals.map(
      (row) =>
        `- You have been referred to ${row.to_name}${
          row.specialty ? ` (${row.specialty})` : ""
        }${URGENCY[row.urgency] ?? ""}.`,
    ),
  ];
  if (next.length > 0) parts.push(["What happens next:", ...next].join("\n"));
  parts.push(SAFETY_NET);
  return parts.join("\n\n");
}
