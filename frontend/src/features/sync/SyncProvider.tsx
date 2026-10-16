"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { SYNCED_QUERIES, deviceOutbox } from "@/lib/sync/device-outbox";
import { retryDelaySeconds, type FlushResult, type NewWrite } from "@/lib/sync/outbox";
import type { OutboxItem } from "@/lib/sync/store";

/*
 * Runs the outbox for the signed-in person: sends on arrival, whenever a write is
 * queued, when the network comes back, and again after a growing wait while it
 * stays away. Screens queue writes through useSync() and read what is waiting.
 */

type SyncContextValue = {
  staffId: string;
  items: OutboxItem[]; // everything on this device, oldest first
  online: boolean;
  stopped: FlushResult["stopped"];
  queue: (write: NewWrite) => Promise<void>;
  discard: (seq: number) => Promise<void>;
};

const SyncContext = createContext<SyncContextValue | null>(null);

export function SyncProvider({ staffId, children }: { staffId: string; children: ReactNode }) {
  const outbox = deviceOutbox();
  const queryClient = useQueryClient();
  const [items, setItems] = useState<OutboxItem[]>([]);
  const [online, setOnline] = useState(true);
  const [stopped, setStopped] = useState<FlushResult["stopped"]>(null);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);
  const misses = useRef(0);

  const send = useCallback(async () => {
    if (retry.current) clearTimeout(retry.current);
    retry.current = null;
    let result: FlushResult;
    try {
      result = await outbox.flush(staffId);
    } catch {
      result = { sent: 0, failed: 0, stopped: "offline" }; // the device store itself failed
    }
    setStopped(result.stopped);
    if (result.sent > 0 || result.failed > 0) {
      for (const key of SYNCED_QUERIES) void queryClient.invalidateQueries({ queryKey: [key] });
    }
    if (result.stopped === "offline") {
      misses.current += 1;
      retry.current = setTimeout(() => void send(), retryDelaySeconds(misses.current) * 1000);
    } else {
      misses.current = 0;
    }
  }, [outbox, staffId, queryClient]);

  useEffect(() => {
    const refresh = () => {
      outbox.items().then(setItems, () => setItems([]));
    };
    refresh();
    return outbox.subscribe(refresh);
  }, [outbox]);

  useEffect(() => {
    setOnline(navigator.onLine);
    const up = () => {
      setOnline(true);
      void send();
    };
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    void send(); // anything left from before a reload or a new sign-in
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
      if (retry.current) clearTimeout(retry.current);
    };
  }, [send]);

  const queue = useCallback(
    async (write: NewWrite) => {
      await outbox.enqueue({ ...write, staffId });
      void send();
    },
    [outbox, staffId, send],
  );
  const discard = useCallback((seq: number) => outbox.discard(seq), [outbox]);

  return (
    <SyncContext.Provider value={{ staffId, items, online, stopped, queue, discard }}>
      {children}
    </SyncContext.Provider>
  );
}

export function useSync(): SyncContextValue {
  const value = useContext(SyncContext);
  if (!value) throw new Error("useSync must be used inside SyncProvider.");
  return value;
}
