// Every diary action in plain words. Mirrors backend/app/modules/audit/service.py.
export const ACTION_LABELS: Record<string, string> = {
  "patient.create": "Registered a patient",
  "patient.view": "Opened a patient",
  "patient.search": "Searched for patients",
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
};

/** Plain words for an action; an unknown code is shown as it is, never hidden. */
export function describeAction(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

// Reads are the lines an investigation usually looks for ("who looked at this?").
export function isRead(action: string): boolean {
  return /\.(view|list|search)$/.test(action);
}

// The platform's own actor (the reminder worker). No staff row has this ID.
export const SYSTEM_ACTOR_ID = "00000000-0000-0000-0000-000000000000";
