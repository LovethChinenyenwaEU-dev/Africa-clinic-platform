import { beforeEach, describe, expect, it, vi } from "vitest";

import { countResources, exportFileName, exportRecord } from "./api";

const fetchMock = vi.fn();

const BUNDLE = {
  resourceType: "Bundle",
  id: "b1",
  type: "collection",
  entry: [
    { fullUrl: "urn:uuid:p1", resource: { resourceType: "Patient", id: "p1" } },
    { fullUrl: "urn:uuid:o1", resource: { resourceType: "Observation", id: "o1" } },
    { fullUrl: "urn:uuid:o2", resource: { resourceType: "Observation", id: "o2" } },
  ],
};

function answer(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

describe("exportRecord", () => {
  it("asks the staff pass-through, with the reason", async () => {
    fetchMock.mockResolvedValueOnce(answer(BUNDLE));

    const bundle = await exportRecord("11111111-1111-4111-8111-111111111111", "referral");

    expect(bundle.entry).toHaveLength(3);
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/api/backend/interop/patients/11111111-1111-4111-8111-111111111111/fhir?reason=referral",
    );
  });

  it("refuses anything that is not a FHIR collection bundle", async () => {
    fetchMock.mockResolvedValueOnce(answer({ resourceType: "Patient" }));

    await expect(exportRecord("p", "patient_request")).rejects.toThrow();
  });

  it("shows the backend's own words when consent to sharing is missing", async () => {
    fetchMock.mockResolvedValueOnce(
      answer({ detail: "The patient has not agreed to share their record." }, 409),
    );

    await expect(exportRecord("p", "transfer")).rejects.toThrow(/not agreed to share/);
  });
});

describe("the file", () => {
  it("is named by part of the ID and the day, never the patient's name", () => {
    expect(exportFileName("11111111-1111-4111-8111-111111111111", "2026-11-02")).toBe(
      "patient-record-11111111-2026-11-02.fhir.json",
    );
  });

  it("counts what is in it", () => {
    expect(countResources(BUNDLE as never)).toEqual({ Patient: 1, Observation: 2 });
  });
});
