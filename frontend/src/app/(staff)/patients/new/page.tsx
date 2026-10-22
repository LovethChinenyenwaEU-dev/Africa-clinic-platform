import { redirect } from "next/navigation";

import { can } from "@/features/identity/abilities";
import { RegisterPatientForm } from "@/features/patients/RegisterPatientForm";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Register a patient | Lafiya" };

export default async function RegisterPatientPage() {
  const user = await requireUser("patients");
  if (!can(user.role, "register_patient")) {
    redirect("/patients");
  }
  return <RegisterPatientForm />;
}
