import { redirect } from "next/navigation";

import { Logo } from "@/components/brand/Logo";
import { LoginForm } from "@/features/identity/LoginForm";
import { getCurrentUser } from "@/lib/server/current-user";
import { landingUrl } from "@/lib/server/landing";

export const metadata = { title: "Sign in | Lafiya" };

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
      <a href={landingUrl()} aria-label="About the platform" className="mb-8 inline-block">
        <Logo tagline />
      </a>
      <h1>Sign in</h1>
      <LoginForm />
      <p className="mt-6 text-sm text-muted">
        New here? <a href={landingUrl()} className="font-bold text-accent">See what it does</a>
      </p>
    </main>
  );
}
