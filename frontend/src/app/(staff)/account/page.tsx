import { DeviceList } from "@/features/identity/DeviceList";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "My devices | AfriPeak Health" };

// Every role, for their own devices only (Week 11).
export default async function AccountPage() {
  await requireUser("account");
  return <DeviceList />;
}
