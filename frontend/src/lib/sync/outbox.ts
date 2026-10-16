import { z } from "zod";

import { ApiError, apiPost } from "@/lib/api-client";

import type { OutboxItem, OutboxStore } from "./store";

/*
 * The outbox: writes made on this device wait here and are sent, oldest first,
 * when the server can be reached (FR-O1..O3).
 *
 * Every queued write keeps the same Idempotency-Key for its whole life, so sending
 * it again after a dropped connection can never record it twice: the server
 * answers a repeat with its first answer.
 *
 * What happens to each answer:
 * - Accepted: removed from the outbox.
 * - No network, or the server is down: stop and keep everything, in order. Try later.
 * - Signed out: stop and keep everything. Nothing is lost while the person signs in again.
 * - Refused for good (not allowed, not found, invalid, conflicting move): kept and
 *   marked failed with the server's reason, so a person can look at it. The writes
 *   behind it carry on.
 */

export type NewWrite = {
  path: string;
  body: unknown;
  label: string;
  encounterId?: string | null;
};

// A write as the screen queues it, with who is making it.
export type StaffWrite = NewWrite & { staffId: string };

export type FlushResult = {
  sent: number;
  failed: number;
  stopped: null | "offline" | "signed_out";
};

export type Deliver = (item: OutboxItem) => Promise<unknown>;

// Sends one queued write. The answer's shape is checked by the screen that reads it later.
export const deliverByPost: Deliver = (item) =>
  apiPost(item.path, item.body, z.unknown(), { idempotencyKey: item.id });

const PERMANENT = new Set(["forbidden", "not_found", "invalid", "conflict"]);

/** Seconds to wait before trying again: 2, 4, 8 ... up to one minute. */
export function retryDelaySeconds(attempts: number): number {
  return Math.min(60, 2 ** Math.max(1, attempts));
}

export class Outbox {
  private running: Promise<FlushResult> | null = null;
  private readonly listeners = new Set<() => void>();

  constructor(
    private readonly store: OutboxStore,
    private readonly deliver: Deliver = deliverByPost,
    private readonly now: () => Date = () => new Date(),
  ) {}

  /** Queue a write. It is safe on the device from this moment. */
  async enqueue(write: StaffWrite): Promise<OutboxItem> {
    const item = await this.store.add({
      id: crypto.randomUUID(),
      path: write.path,
      body: write.body,
      label: write.label,
      staffId: write.staffId,
      encounterId: write.encounterId ?? null,
      createdAt: this.now().toISOString(),
      attempts: 0,
      status: "pending",
      error: null,
    });
    this.changed();
    return item;
  }

  /** Everything still on the device, oldest first: waiting and failed. */
  items(): Promise<OutboxItem[]> {
    return this.store.list();
  }

  /**
   * Send what this person queued. Someone else's writes are never sent under this
   * session: they wait for their own author to sign in on this device again.
   * Calls made while a send is running share it.
   */
  flush(staffId: string): Promise<FlushResult> {
    this.running ??= this.sendAll(staffId).finally(() => {
      this.running = null;
    });
    return this.running;
  }

  /** Be told when anything in the outbox changes (for badges and the sync indicator). */
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private changed() {
    for (const listener of this.listeners) listener();
  }

  /** Remove a write a person has looked at and let go (one the server refused). */
  async discard(seq: number): Promise<void> {
    await this.store.remove(seq);
    this.changed();
  }

  private async sendAll(staffId: string): Promise<FlushResult> {
    const result: FlushResult = { sent: 0, failed: 0, stopped: null };
    const waiting = (await this.store.list()).filter(
      (item) => item.status === "pending" && item.staffId === staffId,
    );

    for (const item of waiting) {
      try {
        await this.deliver(item);
        await this.store.remove(item.seq);
        result.sent += 1;
        this.changed();
      } catch (error) {
        const kind = error instanceof ApiError ? error.kind : "unavailable";
        if (kind === "signed_out") {
          result.stopped = "signed_out";
          break;
        }
        if (PERMANENT.has(kind)) {
          const message = error instanceof ApiError ? error.message : String(kind);
          await this.store.put({
            ...item,
            attempts: item.attempts + 1,
            status: "failed",
            error: message,
          });
          result.failed += 1;
          this.changed();
          continue;
        }
        // Offline, a server error, or anything unexpected: try again later, in order.
        await this.store.put({ ...item, attempts: item.attempts + 1 });
        result.stopped = "offline";
        this.changed();
        break;
      }
    }
    return result;
  }
}
