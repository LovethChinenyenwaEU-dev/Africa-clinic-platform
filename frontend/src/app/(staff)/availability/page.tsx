import { MyHours } from "@/features/scheduling/MyHours";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "My hours | AfriPeak Health" };

// Doctors and nurses publish their own weekly hours (FR-C1).
export default async function AvailabilityPage() {
  const user = await requireUser("availability");
  return <MyHours meId={user.id} />;
}
