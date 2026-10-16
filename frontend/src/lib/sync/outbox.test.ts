import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

import { Outbox, deliverByPost, retryDelaySeconds, type Deliver } from "./outbox";
import { memoryStore, type OutboxItem } from "./store";

const ENCOUNTER = "33333333-3333-4333-8333-333333333333";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function vitals(pulse: number) {
  return {
    path: `/encounters/${ENCOUNTER}/vitals`,
    body: { pulse_bpm: pulse },
    label: "Vitals",
    encounterId: ENCOUNTER,
  };
}

// A pretend server: answers each send with the next result in the list.
function server(...results: Array<"ok" | Error>) {
  const sent: OutboxItem[] = [];
  const deliver: Deliver = async (item) => {
    sent.push(item);
    const next = results.shift() ?? "ok";
    if (next !== "ok") throw next;
    return { id: item.id };
  };
  return { sent, deliver };
}

let fakeServer: ReturnType<typeof server>;

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("queueing", () => {
  it("keeps each write with its own idempotency key, oldest first", async () => {
    const outbox = new Outbox(memoryStore(), server().deliver);

    const first = await outbox.enqueue(vitals(80));
    const second = await outbox.enqueue(vitals(90));

    expect(first.id).toMatch(UUID);
    expect(second.id).not.toBe(first.id);
    const items = await outbox.items();
    expect(items.map((item) => item.body)).toEqual([{ pulse_bpm: 80 }, { pulse_bpm: 90 }]);
    expect(items.every((item) => item.status === "pending" && item.attempts === 0)).toBe(true);
    expect(items[0].encounterId).toBe(ENCOUNTER);
  });
});

describe("flush", () => {
  it("sends in order and empties the outbox", async () => {
    fakeServer = server();
    const outbox = new Outbox(memoryStore(), fakeServer.deliver);
    await outbox.enqueue(vitals(80));
    await outbox.enqueue(vitals(90));

    const result = await outbox.flush();

    expect(result).toEqual({ sent: 2, failed: 0, stopped: null });
    expect(fakeServer.sent.map((item) => item.body)).toEqual([
      { pulse_bpm: 80 },
      { pulse_bpm: 90 },
    ]);
    expect(await outbox.items()).toEqual([]);
  });

  it("stops when offline, keeps everything in order, and re-sends with the same key", async () => {
    fakeServer = server(new ApiError("unavailable"));
    const outbox = new Outbox(memoryStore(), fakeServer.deliver);
    const first = await outbox.enqueue(vitals(80));
    await outbox.enqueue(vitals(90));

    const offline = await outbox.flush();

    expect(offline).toEqual({ sent: 0, failed: 0, stopped: "offline" });
    expect(fakeServer.sent).toHaveLength(1); // the second was not tried out of order
    const waiting = await outbox.items();
    expect(waiting.map((item) => item.attempts)).toEqual([1, 0]);

    const online = await outbox.flush();

    expect(online).toEqual({ sent: 2, failed: 0, stopped: null });
    expect(fakeServer.sent[1].id).toBe(first.id); // same key: the server cannot do it twice
  });

  it("treats an unexpected error like no network: keep and try later", async () => {
    fakeServer = server(new TypeError("Failed to fetch"));
    const outbox = new Outbox(memoryStore(), fakeServer.deliver);
    await outbox.enqueue(vitals(80));

    expect((await outbox.flush()).stopped).toBe("offline");
    expect(await outbox.items()).toHaveLength(1);
  });

  it("keeps everything, untouched, when the session has ended", async () => {
    fakeServer = server(new ApiError("signed_out"));
    const outbox = new Outbox(memoryStore(), fakeServer.deliver);
    await outbox.enqueue(vitals(80));
    await outbox.enqueue(vitals(90));

    const result = await outbox.flush();

    expect(result.stopped).toBe("signed_out");
    const waiting = await outbox.items();
    expect(waiting).toHaveLength(2);
    expect(waiting.every((item) => item.status === "pending" && item.attempts === 0)).toBe(true);
  });

  it("marks a write the server refused for good, with its reason, and carries on", async () => {
    const reason = "New vitals can only be added to an open encounter.";
    fakeServer = server(new ApiError("conflict", reason));
    const outbox = new Outbox(memoryStore(), fakeServer.deliver);
    await outbox.enqueue(vitals(80));
    await outbox.enqueue(vitals(90));

    const result = await outbox.flush();

    expect(result).toEqual({ sent: 1, failed: 1, stopped: null });
    const [refused] = await outbox.items();
    expect(refused.status).toBe("failed");
    expect(refused.error).toBe(reason);

    await outbox.flush();

    expect(fakeServer.sent).toHaveLength(2); // a refused write is not sent again by itself
  });

  it.each(["forbidden", "not_found", "invalid", "conflict"] as const)(
    "counts %s as refused for good",
    async (kind) => {
      const outbox = new Outbox(memoryStore(), server(new ApiError(kind)).deliver);
      await outbox.enqueue(vitals(80));

      expect((await outbox.flush()).failed).toBe(1);
    },
  );

  it("never runs two sends at once: a second call shares the first", async () => {
    let release: () => void = () => {};
    const deliver = vi.fn<Deliver>(
      () => new Promise((resolve) => (release = () => resolve({}))),
    );
    const outbox = new Outbox(memoryStore(), deliver);
    await outbox.enqueue(vitals(80));

    const first = outbox.flush();
    const second = outbox.flush();
    await vi.waitFor(() => expect(deliver).toHaveBeenCalledTimes(1));
    release();

    expect(await first).toEqual(await second);
    expect(deliver).toHaveBeenCalledTimes(1);
  });

  it("tells listeners when something changes", async () => {
    const outbox = new Outbox(memoryStore(), server().deliver);
    const listener = vi.fn();
    const stop = outbox.subscribe(listener);

    await outbox.enqueue(vitals(80));
    await outbox.flush();
    stop();
    await outbox.enqueue(vitals(90));

    expect(listener).toHaveBeenCalledTimes(2); // queued, then sent; nothing after stop
  });
});

describe("retryDelaySeconds", () => {
  it("doubles, and never waits more than a minute", () => {
    expect([0, 1, 2, 3, 5, 6, 20].map(retryDelaySeconds)).toEqual([2, 2, 4, 8, 32, 60, 60]);
  });
});

describe("deliverByPost", () => {
  it("posts the queued body with the item's idempotency key", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ id: "x" }), {
          status: 201,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const outbox = new Outbox(memoryStore());
    const item = await outbox.enqueue(vitals(80));

    await deliverByPost(item);

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(url).toBe(`/api/backend/encounters/${ENCOUNTER}/vitals`);
    expect(headers["Idempotency-Key"]).toBe(item.id);
    expect(JSON.parse(init.body as string)).toEqual({ pulse_bpm: 80 });
    vi.unstubAllGlobals();
  });
});
