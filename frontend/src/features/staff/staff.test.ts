import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  endStaffDevice,
  listStaff,
  newStaffSchema,
  resetApp,
  setActive,
  sortStaff,
  type StaffListItem,
} from "./api";

const fetchMock = vi.fn();
const ID = "11111111-1111-4111-8111-111111111111";
const DEVICE = "22222222-2222-4222-8222-222222222222";

function person(name: string, isActive = true): StaffListItem {
  return {
    id: ID,
    email: `${name.toLowerCase()}@clinic.example`,
    full_name: name,
    role: "nurse",
    is_active: isActive,
    mfa: "not_needed",
  };
}

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function sent(call = 0) {
  const [url, init] = fetchMock.mock.calls[call];
  return { url: String(url), method: init?.method };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("the new staff form", () => {
  const good = {
    full_name: " Ada Obi ",
    email: "ada@clinic.example",
    role: "nurse",
    password: "long-enough-1",
  };

  it("accepts a proper form and trims the name", () => {
    const parsed = newStaffSchema.parse(good);
    expect(parsed.full_name).toBe("Ada Obi");
  });

  it("refuses a short password, a bad email and an unknown role before asking the server", () => {
    expect(newStaffSchema.safeParse({ ...good, password: "short" }).success).toBe(false);
    expect(newStaffSchema.safeParse({ ...good, email: "not-an-email" }).success).toBe(false);
    expect(newStaffSchema.safeParse({ ...good, role: "wizard" }).success).toBe(false);
  });
});

describe("the list", () => {
  it("puts active people first, then by name", () => {
    const sorted = sortStaff([person("Zainab"), person("Bola", false), person("Ade")]);
    expect(sorted.map((p) => p.full_name)).toEqual(["Ade", "Zainab", "Bola"]);
  });

  it("reads the staff with where each authenticator app stands", async () => {
    fetchMock.mockResolvedValueOnce(answer([{ ...person("Ade"), mfa: "waiting" }]));

    const people = await listStaff();

    expect(people[0].mfa).toBe("waiting");
    expect(sent().url).toContain("/api/backend/staff");
  });
});

describe("the actions", () => {
  it("switches a person off and on with the right address", async () => {
    fetchMock.mockResolvedValue(answer(person("Ade")));

    await setActive(ID, false);
    await setActive(ID, true);

    expect(sent(0)).toEqual({ url: `/api/backend/staff/${ID}/deactivate`, method: "POST" });
    expect(sent(1)).toEqual({ url: `/api/backend/staff/${ID}/activate`, method: "POST" });
  });

  it("ends one device and resets an app", async () => {
    fetchMock.mockResolvedValueOnce(answer({ signed_out: true }));
    fetchMock.mockResolvedValueOnce(answer({ reset: true }));

    await endStaffDevice(ID, DEVICE);
    await resetApp(ID);

    expect(sent(0).url).toBe(`/api/backend/staff/${ID}/sessions/${DEVICE}/end`);
    expect(sent(1).url).toBe(`/api/backend/staff/${ID}/mfa/reset`);
  });

  it("shows the backend's reason when it refuses (for example the last admin)", async () => {
    fetchMock.mockResolvedValueOnce(answer({ detail: "The clinic needs at least one admin." }, 409));

    await expect(setActive(ID, false)).rejects.toThrow(/at least one admin/);
  });
});
