import { redirect } from "next/navigation";

import { LoginForm } from "@/features/identity/LoginForm";
import { getCurrentUser } from "@/lib/server/current-user";

export const metadata = { title: "Sign in | Clinic Platform" };

export default async function LoginPage() {
  let signedIn = false;
  try {
    signedIn = (await getCurrentUser()) !== null;
  } catch {
    // The backend is unreachable. Show the form anyway: signing in will say "unavailable".
  }
  if (signedIn) {
    redirect("/");
  }

  return (
    <main className="page">
      <h1>Sign in</h1>
      <LoginForm />
    </main>
  );
}