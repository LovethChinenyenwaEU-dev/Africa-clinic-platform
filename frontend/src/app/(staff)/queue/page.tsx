import { can } from "@/features/identity/abilities";
import { QueueBoard } from "@/features/scheduling/QueueBoard";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Today's queue | AfriPeak Health" };

export default async function QueuePage() {
  const user = await requireUser("queue");
  return <QueueBoard canConsult={can(user.role, "run_consultation")} />;
}
