"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useSync } from "@/features/sync/SyncProvider";
import { signOutBlock, syncView } from "@/lib/sync/summary";

import { logout } from "./api";

export function SignOutButton() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { staffId, items, online, stopped } = useSync();
  const [refusal, setRefusal] = useState<string | null>(null);

  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear(); // no patient data stays in this tab's memory
      router.replace("/login");
      router.refresh();
    },
  });

  function handleClick() {
    // Signing out with writes still on the device would strand them: wait until they are sent.
    const blocked = signOutBlock(syncView(items, staffId, online, stopped));
    setRefusal(blocked);
    if (!blocked) signOut.mutate();
  }

  return (
    <div>
      <button className="button" type="button" onClick={handleClick} disabled={signOut.isPending}>
        {signOut.isPending ? "Signing out..." : "Sign out"}
      </button>
      {refusal && (
        <p role="alert" className="error max-w-xs">
          {refusal}
        </p>
      )}
      {signOut.error && (
        <p role="alert" className="error">
          {signOut.error.message}
        </p>
      )}
    </div>
  );
}
