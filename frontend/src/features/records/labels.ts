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
