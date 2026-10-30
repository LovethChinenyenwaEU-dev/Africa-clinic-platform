import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/Logo";
import { navFor } from "@/features/identity/navigation";
import { ROLE_LABELS } from "@/features/identity/roles";
import { SignOutButton } from "@/features/identity/SignOutButton";
import { StaffNav } from "@/features/identity/StaffNav";
import { OfflineReads } from "@/features/sync/OfflineReads";
import { SyncIndicator } from "@/features/sync/SyncIndicator";
import { SyncProvider } from "@/features/sync/SyncProvider";
import { requireUser } from "@/lib/server/require-user";

// Every staff screen sits inside this frame. Nobody signed in never sees it.
// The sync provider sends this person's offline writes from any screen.
export default async function StaffLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();

  return (
    <SyncProvider staffId={user.id}>
      <div className="min-h-screen">
        {/* The AfriPeak Health frame: a thin deep-green bar, then a white sticky header. */}
        <div className="bg-accent-dark text-xs text-[#d8e7f2] print:hidden">
          <div className="mx-auto flex min-h-9 max-w-6xl flex-wrap items-center justify-between gap-x-4 px-4">
            <span>
              Signed in as <strong className="text-white">{user.full_name}</strong> ·{" "}
              {ROLE_LABELS[user.role]}
            </span>
            <span className="hidden tracking-wide text-[#a9c3d5] sm:inline">
              Connected care, built for the realities of Africa
            </span>
          </div>
        </div>
        <header className="sticky top-0 z-40 border-b border-line bg-white print:hidden">
          <div className="mx-auto flex min-h-[4.5rem] max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-2">
            <Link href="/" aria-label="AfriPeak Health, home">
              <Logo size="sm" tagline />
            </Link>
            <StaffNav items={navFor(user.role)} />
            <div className="ml-auto flex items-center gap-3 text-sm">
              <SyncIndicator />
              <SignOutButton />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">
          <OfflineReads staffId={user.id}>{children}</OfflineReads>
        </main>
      </div>
    </SyncProvider>
  );
}
