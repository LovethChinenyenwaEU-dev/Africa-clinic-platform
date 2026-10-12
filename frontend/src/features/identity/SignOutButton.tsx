"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { logout } from "./api";

export function SignOutButton() {
  const router = useRouter();
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      router.replace("/login");
      router.refresh();
    },
  });

  return (
    <div>
      <button
        className="button"
        type="button"
        onClick={() => signOut.mutate()}
        disabled={signOut.isPending}
      >
        {signOut.isPending ? "Signing out..." : "Sign out"}
      </button>
      {signOut.error && (
        <p role="alert" className="error">
          {signOut.error.message}
        </p>
      )}
    </div>
  );
}