"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { signInPageFor } from "@/features/portal/paths";
import { ApiError } from "@/lib/api-client";
import { registerServiceWorker } from "@/lib/sync/service-worker";

// When any screen learns the session has ended, everyone goes back to sign in:
// patients to their clinic's sign-in page, staff to the staff login.
function sendToLoginIfSignedOut(error: unknown) {
  if (error instanceof ApiError && error.kind === "signed_out") {
    window.location.assign(signInPageFor(window.location.pathname));
  }
}

export function Providers({ children }: { children: ReactNode }) {
  // Lets the app open with no network (Week 8).
  useEffect(registerServiceWorker, []);

  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError: sendToLoginIfSignedOut }),
        mutationCache: new MutationCache({ onError: sendToLoginIfSignedOut }),
        defaultOptions: {
          // A clinical write is never sent twice by accident; queries may retry once.
          mutations: { retry: false },
          queries: {
            // Every read of patient data is written in the diary, so never re-read silently
            // when the window regains focus. Screens that need live data (the queue) opt in.
            refetchOnWindowFocus: false,
            retry: (count, error) => !(error instanceof ApiError) && count < 1,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
