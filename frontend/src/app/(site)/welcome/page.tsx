import { redirect } from "next/navigation";

import { landingUrl } from "@/lib/server/landing";

// The public page is now the AfriPeak Health landing page, its own app (landing/).
// The earlier Lafiya page (features/site) is kept but no longer shown.
export default function WelcomePage() {
  redirect(landingUrl());
}
