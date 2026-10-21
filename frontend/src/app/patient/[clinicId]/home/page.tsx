import { notFound, redirect } from "next/navigation";

import { PatientHome } from "@/features/portal/PatientHome";
import { patientSession } from "@/lib/server/session";

export const metadata = { title: "Your clinic record" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// The patient's own page. No patient data is in this HTML: it loads in the browser.
export default async function PatientHomePage({
  params,
}: {
  params: Promise<{ clinicId: string }>;
}) {
  const { clinicId } = await params;
  if (!UUID.test(clinicId)) {
    notFound();
  }
  if (!(await patientSession.read())) {
    redirect(`/patient/${clinicId}`);
  }
  return <PatientHome clinicId={clinicId} />;
}
