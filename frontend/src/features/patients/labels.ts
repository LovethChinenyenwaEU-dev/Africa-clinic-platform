import type { DuplicateMatch } from "./schemas";

export const SEX_LABELS: Record<string, string> = {
  female: "Female",
  male: "Male",
  other: "Other",
};

export const DUPLICATE_REASON_LABELS: Record<DuplicateMatch["reason"], string> = {
  same_phone: "Same phone number",
  same_name_and_birth_date: "Same name and date of birth",
};
