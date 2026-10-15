import { AuditLog } from "@/features/audit/AuditLog";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Audit log | Clinic Platform" };

export default async function AuditPage() {
  await requireUser("audit"); // admins only
  return <AuditLog />;
}
