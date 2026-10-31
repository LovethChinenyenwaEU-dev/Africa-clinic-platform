import { ReminderConsole } from "@/features/notifications/ReminderConsole";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Reminders | AfriPeak Health" };

// The notification console: admins only (Week 11).
export default async function RemindersPage() {
  await requireUser("reminders");
  return <ReminderConsole />;
}
