import { notFound } from "next/navigation";

import { ReferralLetter } from "@/features/records/ReferralLetter";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Referral letter | AfriPeak Health" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function ReferralLetterPage({
  params,
}: {
  params: Promise<{ referralId: string }>;
}) {
  await requireUser("encounter"); // doctors and nurses only
  const { referralId } = await params;
  if (!UUID.test(referralId)) {
    notFound();
  }
  return <ReferralLetter referralId={referralId} />;
}
