export const STATUS_LABELS: Record<string, string> = {
  booked: "Booked",
  waiting: "Waiting",
  in_consult: "With clinician",
  done: "Done",
  cancelled: "Cancelled",
  no_show: "Did not come",
};

// Colours for the status badge. Text and colour together, never colour alone.
export const STATUS_STYLES: Record<string, string> = {
  booked: "bg-blue-100 text-blue-900",
  waiting: "bg-amber-100 text-amber-900",
  in_consult: "bg-green-100 text-green-900",
  done: "bg-gray-200 text-gray-800",
  cancelled: "bg-gray-200 text-gray-800",
  no_show: "bg-red-100 text-red-900",
};

export const KIND_LABELS: Record<string, string> = {
  scheduled: "Appointment",
  walk_in: "Walk-in",
};

// Triage (Week 9). Most urgent first.
export const TRIAGE_LEVELS = ["emergency", "urgent", "standard"] as const;
export type TriageLevel = (typeof TRIAGE_LEVELS)[number];

export const TRIAGE_LABELS: Record<string, string> = {
  emergency: "Emergency: see now",
  urgent: "Urgent: see soon",
  standard: "Standard",
};

export const TRIAGE_STYLES: Record<string, string> = {
  emergency: "bg-red-100 text-red-900",
  urgent: "bg-amber-100 text-amber-900",
  standard: "bg-gray-200 text-gray-800",
};

// Danger signs: any one makes the visit an emergency. Mirrors the backend's RedFlag codes.
export const RED_FLAG_LABELS: Record<string, string> = {
  difficulty_breathing: "Difficulty breathing",
  chest_pain: "Chest pain",
  unconscious_or_confused: "Unconscious or confused",
  convulsions: "Convulsions (fits)",
  severe_bleeding: "Severe bleeding",
  stroke_signs: "Stroke signs (face droop, arm weakness, speech)",
  severe_dehydration: "Severe dehydration",
  fever_with_stiff_neck: "Fever with a stiff neck",
  pregnancy_bleeding_or_pain: "Pregnant with bleeding or severe pain",
  child_unable_to_drink: "Child unable to drink or breastfeed",
  severe_pain: "Severe pain",
  thoughts_of_self_harm: "Thoughts of self-harm",
};

/** The level that will be saved: a danger sign always means emergency (the server agrees). */
export function effectiveLevel(level: TriageLevel, redFlags: string[]): TriageLevel {
  return redFlags.length > 0 ? "emergency" : level;
}
