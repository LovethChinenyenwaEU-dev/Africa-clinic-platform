// Every diary action in plain words. Mirrors backend/app/modules/audit/service.py.
export const ACTION_LABELS: Record<string, string> = {
  "patient.create": "Registered a patient",
  "patient.view": "Opened a patient",
  "patient.search": "Searched for patients",
  "patient.review_list": "Viewed registrations to review",
  "patient.review": "Decided on an offline registration",
  "consent.grant": "Recorded consent",
  "consent.revoke": "Withdrew consent",
  "consent.view": "Viewed consent",
  "audit.view": "Read this audit log",
  "appointment.create": "Booked or registered a visit",
  "appointment.check_in": "Checked a patient in",
  "appointment.start": "Started a consultation",
  "appointment.complete": "Completed a consultation",
  "appointment.cancel": "Cancelled a visit",
  "appointment.no_show": "Marked a no-show",
  "appointment.reschedule": "Rescheduled a visit",
  "queue.view": "Viewed the queue",
  "appointment.list": "Viewed the day's visits",
  "triage.record": "Triaged a patient",
  "triage.view": "Viewed triage history",
  "availability.add": "Published weekly hours",
  "availability.remove": "Removed weekly hours",
  "teleconsult.intake": "Took a remote visit intake",
  "teleconsult.escalate": "Sent a remote patient to in-person care (danger sign)",
  "teleconsult.intake_view": "Read a remote visit intake",
  "teleconsult.room_open": "Opened a consult room",
  "teleconsult.mode": "Switched a consult between video, audio and text",
  "teleconsult.message": "Sent a consult chat message",
  "teleconsult.chat_view": "Opened a consult chat",
  "follow_up.plan": "Planned a follow-up",
  "follow_up.view": "Viewed follow-ups",
  "follow_up.list": "Viewed the follow-ups due",
  "follow_up.booked": "Marked a follow-up booked",
  "follow_up.cancel": "Cancelled a follow-up",
  "referral.write": "Wrote a referral",
  "referral.view": "Viewed a referral",
  "referral.cancel": "Cancelled a referral",
  "summary.draft": "Drafted a patient summary",
  "summary.edit": "Edited a patient summary draft",
  "summary.approve": "Approved a patient summary",
  "summary.withdraw": "Withdrew a patient summary",
  "summary.view": "Viewed patient summaries",
  "portal.code_sent": "Patient asked for a sign-in code",
  "portal.sign_in": "Patient signed in",
  "portal.visits_view": "Patient viewed their visits",
  "portal.summaries_view": "Patient read their summaries",
  "portal.room_view": "Patient joined the consult room",
  "reminder.send": "Sent a reminder",
  "encounter.create": "Opened an encounter",
  "encounter.close": "Signed off an encounter",
  "encounter.entered_in_error": "Marked an encounter as a mistake",
  "encounter.view": "Viewed an encounter",
  "encounter.list": "Viewed a patient's encounters",
  "vitals.record": "Recorded vitals",
  "vitals.correct": "Corrected vitals",
  "vitals.view": "Viewed vitals",
  "allergy.record": "Recorded an allergy",
  "allergy.revise": "Changed an allergy",
  "allergy.view": "Viewed allergies",
  "problem.record": "Recorded a problem or diagnosis",
  "problem.revise": "Changed a problem or diagnosis",
  "problem.view": "Viewed problems",
  "note.write": "Wrote a note",
  "note.amend": "Amended a note",
  "note.view": "Viewed notes",
  "vitals.resolve": "Settled a vitals conflict",
  "allergy.resolve": "Settled an allergy conflict",
  "problem.resolve": "Settled a problem conflict",
  "note.resolve": "Settled a note conflict",
  "prescription.write": "Wrote a prescription",
  "prescription.revise": "Stopped or changed a prescription",
  "prescription.view": "Viewed prescriptions",
  "prescription.resolve": "Settled a prescription conflict",
  "price.add": "Added a service to the price list",
  "price.change": "Changed a price or retired a service",
};

/** Plain words for an action; an unknown code is shown as it is, never hidden. */
export function describeAction(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

// Reads are the lines an investigation usually looks for ("who looked at this?").
export function isRead(action: string): boolean {
  return /[._](view|list|search)$/.test(action); // patient.review_list counts too
}

// The platform's own actor (the reminder worker). No staff row has this ID.
export const SYSTEM_ACTOR_ID = "00000000-0000-0000-0000-000000000000";

// The purpose on lines a patient wrote themselves, from their own web page (Week 9).
export const PATIENT_PORTAL = "patient_portal";
