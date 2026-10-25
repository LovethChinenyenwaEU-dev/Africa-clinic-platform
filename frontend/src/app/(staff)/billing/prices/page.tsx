import { PriceList } from "@/features/billing/PriceList";
import { can } from "@/features/identity/abilities";
import { requireUser } from "@/lib/server/require-user";

export const metadata = { title: "Prices | Lafiya" };

// Everyone who bills reads the price list; only admins change it.
export default async function PricesPage() {
  const user = await requireUser("prices");
  return <PriceList canEdit={can(user.role, "set_prices")} />;
}
