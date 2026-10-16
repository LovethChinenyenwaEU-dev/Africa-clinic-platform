"use client";

import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";

import type { Encounter } from "@/features/records/schemas";
import { deviceReadCache } from "@/lib/sync/device-outbox";
import { keepsOffline, sortSaved, type ReadEntry } from "@/lib/sync/read-cache";

/*
 * Keeps a small copy of this person's reads on the device (see read-cache.ts) and
 * puts it back on screen when the app opens, before any screen asks the network.
 * With a network the screens then refresh as usual; without one they show the copy.
 */

const PURGE_EVERY_MS = 10 * 60 * 1000;

function encounterPatients(client: QueryClient): Set<string> {
  const ids = new Set<string>();
  for (const [, data] of client.getQueriesData<Encounter>({ queryKey: ["encounter"] })) {
    if (data?.patient_id) ids.add(data.patient_id);
  }
  return ids;
}

export function OfflineReads({ staffId, children }: { staffId: string; children: ReactNode }) {
  const client = useQueryClient();
  const [ready, setReady] = useState(false);
  const restoring = useRef(true);

  // Put saved reads back first, so a screen opened offline has something to show.
  useEffect(() => {
    const cache = deviceReadCache();
    let cancelled = false;
    async function restore() {
      try {
        const { usable, expired } = sortSaved(await cache.all(), staffId, Date.now());
        if (expired.length > 0) await cache.remove(expired);
        // Encounters first, so their patients' details count as theirs.
        const order = (entry: ReadEntry) => (entry.queryKey[0] === "encounter" ? 0 : 1);
        for (const entry of [...usable].sort((a, b) => order(a) - order(b))) {
          if (cancelled) return;
          if (client.getQueryData(entry.queryKey) === undefined) {
            client.setQueryData(entry.queryKey, entry.data, { updatedAt: entry.savedAt });
          }
        }
      } catch {
        // No device storage (private mode, blocked): the app simply needs the network.
      } finally {
        restoring.current = false;
        if (!cancelled) setReady(true);
      }
    }
    void restore();
    return () => {
      cancelled = true;
    };
  }, [client, staffId]);

  // Save each fresh read the rules allow. Restored copies are not saved again, so a
  // copy can never outlive its 24 hours by being restored.
  useEffect(() => {
    const cache = deviceReadCache();
    return client.getQueryCache().subscribe((event) => {
      if (restoring.current || event.type !== "updated" || event.action.type !== "success") return;
      const { queryKey, state } = event.query;
      if (state.data === undefined || !keepsOffline(queryKey, encounterPatients(client))) return;
      void cache
        .put({
          key: JSON.stringify(queryKey),
          queryKey: [...queryKey],
          data: state.data,
          staffId,
          savedAt: Date.now(),
        })
        .catch(() => {});
    });
  }, [client, staffId]);

  // A tab left open still lets go of copies older than 24 hours.
  useEffect(() => {
    const timer = setInterval(() => {
      const cache = deviceReadCache();
      void cache
        .all()
        .then((entries) => cache.remove(sortSaved(entries, staffId, Date.now()).expired))
        .catch(() => {});
    }, PURGE_EVERY_MS);
    return () => clearInterval(timer);
  }, [staffId]);

  return ready ? children : <p>Loading...</p>;
}
