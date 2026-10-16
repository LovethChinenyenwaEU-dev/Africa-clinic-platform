"use client";

import Link from "next/link";

import { indicator, syncView, type Tone } from "@/lib/sync/summary";

import { OutboxList } from "./OutboxList";
import { useSync } from "./SyncProvider";

const TONES: Record<Tone, string> = {
  ok: "bg-green-100 text-green-900",
  busy: "bg-blue-100 text-blue-900",
  warn: "bg-amber-100 text-amber-900",
  bad: "bg-red-100 text-red-900",
};

/** One line in the header that says whether everything is saved, with the list behind it. */
export function SyncIndicator() {
  const { staffId, items, online, stopped, discard } = useSync();
  const view = syncView(items, staffId, online, stopped);
  const { text, tone } = indicator(view);
  const mine = items.filter((item) => item.staffId === staffId);

  return (
    <details className="relative">
      <summary className={`badge cursor-pointer ${TONES[tone]}`} aria-live="polite">
        {text}
      </summary>
      <div className="card absolute right-0 z-10 mt-2 grid w-80 max-w-[90vw] gap-2 sm:w-96">
        {mine.length === 0 ? (
          <p className="text-sm">Everything you entered on this device has been saved.</p>
        ) : (
          <OutboxList items={mine} onDiscard={discard} linkToEncounter />
        )}
        {stopped === "signed_out" && view.waiting > 0 && (
          <p className="text-sm">
            Your session ended. They are kept on this device:{" "}
            <Link href="/login" className="text-accent underline">
              sign in again
            </Link>{" "}
            and they will be sent.
          </p>
        )}
        {view.othersWaiting > 0 && (
          <p className="text-sm">
            {view.othersWaiting} more entered by another staff member wait on this device until
            they sign in here again. They are never sent under your name.
          </p>
        )}
      </div>
    </details>
  );
}
