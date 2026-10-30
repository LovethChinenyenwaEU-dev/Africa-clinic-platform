import { redirect } from "next/navigation";

import { Logo } from "@/components/brand/Logo";
import { LoginForm } from "@/features/identity/LoginForm";
import { getCurrentUser } from "@/lib/server/current-user";
import { landingUrl } from "@/lib/server/landing";

export const metadata = { title: "Sign in | AfriPeak Health" };

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
      <a href={landingUrl()} aria-label="About AfriPeak Health" className="mb-10 inline-block">
        <Logo tagline />
      </a>
      <p className="eyebrow">Staff sign in</p>
      <h1>Welcome back</h1>
      <p className="mb-6 text-muted">
        Sign in to see today&apos;s patients, records and payments.
      </p>
      <LoginForm />
      <p className="mt-6 text-sm text-muted">
        New here?{" "}
        <a href={landingUrl()} className="font-bold text-accent hover:text-teal">
          See what AfriPeak Health does
        </a>
      </p>
    </main>
  );
}
