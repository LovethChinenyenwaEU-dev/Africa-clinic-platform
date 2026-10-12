import type { Role } from "./schemas";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  front_desk: "Front desk",
  nurse: "Nurse",
  doctor: "Doctor",
  billing: "Billing",
};