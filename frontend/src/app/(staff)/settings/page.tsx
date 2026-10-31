import { ClinicSettings } from "@/features/settings/ClinicSettings";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Clinic settings | AfriPeak Health" };

// Branches and consent wording: admins only (Week 11).
export default async function SettingsPage() {
  await requireUser("settings");
  return <ClinicSettings />;
}
