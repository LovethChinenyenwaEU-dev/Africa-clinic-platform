import { notFound } from "next/navigation";

import { can } from "@/features/identity/abilities";
import { PatientDetails } from "@/features/patients/PatientDetails";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Patient | Clinic Platform" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function PatientPage({
  params,
}: {
  params: Promise<{ patientId: string }>;
}) {
  const user = await requireUser("patients");
  const { patientId } = await params;
  if (!UUID.test(patientId)) {
    notFound(); // not even a patient ID: no need to ask the backend
  }
  return (
    <PatientDetails patientId={patientId} canManageConsent={can(user.role, "manage_consent")} />
  );
}
