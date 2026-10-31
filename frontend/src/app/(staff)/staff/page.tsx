import { StaffAdmin } from "@/features/staff/StaffAdmin";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Staff | AfriPeak Health" };

// Admins manage the clinic's staff: add, switch off and on, devices, app resets (Week 11).
export default async function StaffPage() {
  const user = await requireUser("staff");
  return <StaffAdmin meId={user.id} />;
}
