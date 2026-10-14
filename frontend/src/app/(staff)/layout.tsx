import Link from "next/link";
import type { ReactNode } from "react";

import { navFor } from "@/features/identity/navigation";
import { ROLE_LABELS } from "@/features/identity/roles";
import { SignOutButton } from "@/features/identity/SignOutButton";
import { StaffNav } from "@/features/identity/StaffNav";
import { requireUser } from "@/lib/server/require-user";

// Every staff screen sits inside this frame. Nobody signed in never sees it.
export default async function StaffLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link href="/" className="font-bold text-accent">
            Clinic Platform
          </Link>
          <StaffNav items={navFor(user.role)} />
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span>
              {user.full_name} · {ROLE_LABELS[user.role]}
            </span>
            <SignOutButton />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  );
}
