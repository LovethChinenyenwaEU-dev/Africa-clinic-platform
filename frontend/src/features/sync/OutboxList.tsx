"use client";

import Link from "next/link";
import { useState } from "react";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { formatTime } from "@/lib/format";
import type { OutboxItem } from "@/lib/sync/store";

/*
 * The writes still on this device. Only the plain label is shown ("Vitals"), never
 * what was written: the list can appear on any screen.
 */
export function OutboxList({
  items,
  onDiscard,
  linkToEncounter = false,
}: {
  items: OutboxItem[];
  onDiscard: (seq: number) => Promise<void>;
  linkToEncounter?: boolean;
}) {
  const [discarding, setDiscarding] = useState<number | null>(null);

  async function discard(seq: number) {
    setDiscarding(seq);
    try {
      await onDiscard(seq);
    } finally {
      setDiscarding(null);
    }
  }

  return (
    <ul className="grid gap-2">
      {items.map((item) => (
        <li key={item.seq} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="font-mono">{formatTime(item.createdAt)}</span>
          <span className="font-semibold">{item.label}</span>
          {item.status === "pending" ? (
            <span className="badge bg-amber-100 text-amber-900">Waiting to sync</span>
          ) : (
            <>
              <span className="badge bg-red-100 text-red-900">Not saved</span>
              <span>{item.error}</span>
            </>
          )}
          {linkToEncounter && item.encounterId && (
            <Link href={`/encounters/${item.encounterId}`} className="text-accent underline">
              Open encounter
            </Link>
          )}
          {item.status === "failed" && (
            <ConfirmAction
              label="Dismiss"
              question="Dismiss? What was entered is removed from this device for good."
              pending={discarding === item.seq}
              onConfirm={() => void discard(item.seq)}
            />
          )}
        </li>
      ))}
    </ul>
  );
}
