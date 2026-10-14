import { QueueBoard } from "@/features/scheduling/QueueBoard";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Today's queue | Clinic Platform" };

export default async function QueuePage() {
  await requireUser("queue");
  return <QueueBoard />;
}
