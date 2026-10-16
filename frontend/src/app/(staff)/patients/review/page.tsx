import { redirect } from "next/navigation";

import { can } from "@/features/identity/abilities";
import { ReviewQueue } from "@/features/patients/ReviewQueue";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Registrations to review | Clinic Platform" };

// Whoever may register patients decides on offline registrations (backend: patient:write).
export default async function ReviewPage() {
  const user = await requireUser("patients");
  if (!can(user.role, "register_patient")) {
    redirect("/patients");
  }
  return <ReviewQueue />;
}
