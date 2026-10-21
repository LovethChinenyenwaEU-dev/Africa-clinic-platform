import { notFound, redirect } from "next/navigation";

import { patientHome } from "@/features/portal/paths";
import { PatientSignIn } from "@/features/portal/PatientSignIn";
import { patientSession } from "@/lib/server/session";

export const metadata = { title: "Sign in | Your clinic record" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// The link a clinic shares with its patients: /patient/<clinic ID>.
export default async function PatientSignInPage({
  params,
}: {
  params: Promise<{ clinicId: string }>;
}) {
  const { clinicId } = await params;
  if (!UUID.test(clinicId)) {
    notFound();
  }
  if (await patientSession.read()) {
    redirect(patientHome(clinicId)); // an expired session comes straight back here
  }
  return <PatientSignIn clinicId={clinicId} />;
}
