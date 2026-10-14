import { notFound } from "next/navigation";

import { EncounterScreen } from "@/features/records/EncounterScreen";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Encounter | Clinic Platform" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function EncounterPage({
  params,
}: {
  params: Promise<{ encounterId: string }>;
}) {
  const user = await requireUser("encounter"); // doctors and nurses only
  const { encounterId } = await params;
  if (!UUID.test(encounterId)) {
    notFound();
  }
  return <EncounterScreen encounterId={encounterId} meId={user.id} />;
}
