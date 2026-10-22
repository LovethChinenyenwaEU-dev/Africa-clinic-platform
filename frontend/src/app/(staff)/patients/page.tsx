import { can } from "@/features/identity/abilities";
import { PatientSearch } from "@/features/patients/PatientSearch";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Patients | Lafiya" };

export default async function PatientsPage() {
  const user = await requireUser("patients");
  return <PatientSearch canRegister={can(user.role, "register_patient")} />;
}
