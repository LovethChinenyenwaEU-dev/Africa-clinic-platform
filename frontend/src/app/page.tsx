import { redirect } from "next/navigation";

import { ROLE_LABELS } from "@/features/identity/roles";
import { SignOutButton } from "@/features/identity/SignOutButton";
import { getCurrentUser } from "@/lib/server/current-user";

export default async function Home() {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <main className="page">
      <h1>Clinic Platform</h1>
      <p>
        Signed in as {user.full_name} ({ROLE_LABELS[user.role]})
      </p>
      <SignOutButton />
    </main>
  );
}