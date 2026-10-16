import type { ReadingField } from "./schemas";

export const READING_LABELS: Record<ReadingField, { label: string; unit: string }> = {
  systolic_mmhg: { label: "BP systolic", unit: "mmHg" },
  diastolic_mmhg: { label: "BP diastolic", unit: "mmHg" },
  pulse_bpm: { label: "Pulse", unit: "/min" },
  respiratory_rate: { label: "Breathing rate", unit: "/min" },
  spo2_pct: { label: "SpO₂", unit: "%" },
  temperature_c: { label: "Temperature", unit: "°C" },
  weight_kg: { label: "Weight", unit: "kg" },
  height_cm: { label: "Height", unit: "cm" },
};

export const SEVERITY_LABELS: Record<string, string> = {
  mild: "Mild",
  moderate: "Moderate",
  severe: "Severe",
  unknown: "Severity unknown",
};

export const CATEGORY_LABELS: Record<string, string> = {
  encounter_diagnosis: "Diagnosis for this visit",
  problem_list: "Ongoing problem",
};

export const NOTE_KIND_LABELS: Record<string, string> = {
  history: "History",
  examination: "Examination",
  assessment: "Assessment",
  plan: "Plan",
  progress: "Progress",
};

export const ENCOUNTER_STATUS_LABELS: Record<string, string> = {
  open: "Open",
  closed: "Signed off",
  entered_in_error: "Opened by mistake",
};

export const ROUTE_LABELS: Record<string, string> = {
  oral: "By mouth",
  iv: "Into a vein (IV)",
  im: "Into a muscle (IM)",
  sc: "Under the skin (SC)",
  topical: "On the skin",
  inhaled: "Inhaled",
  rectal: "Rectal",
  vaginal: "Vaginal",
  eye: "Eye",
  ear: "Ear",
  nasal: "Nose",
  other: "Other",
};

export const URGENCY_LABELS: Record<string, string> = {
  routine: "Routine",
  urgent: "Urgent (within days)",
  emergency: "Emergency (go now)",
};

export const FOLLOW_UP_STATUS_LABELS: Record<string, string> = {
  planned: "To be booked",
  booked: "Booked",
  cancelled: "Cancelled",
};
