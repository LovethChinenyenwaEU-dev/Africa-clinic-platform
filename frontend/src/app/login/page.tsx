import Link from "next/link";
import { redirect } from "next/navigation";

import { Logo } from "@/components/brand/Logo";
import { LoginForm } from "@/features/identity/LoginForm";
import { getCurrentUser } from "@/lib/server/current-user";

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
      <Link href="/welcome" aria-label="About Lafiya" className="mb-8 inline-block">
        <Logo tagline />
      </Link>
      <h1>Sign in</h1>
      <LoginForm />
      <p className="mt-6 text-sm text-muted">
        New to Lafiya? <Link href="/welcome" className="font-bold text-accent">See what it does</Link>
      </p>
    </main>
  );
}
