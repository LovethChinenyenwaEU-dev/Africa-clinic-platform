import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

import {
  decideReview,
  getPatient,
  getReviewQueue,
  offlineRegistrationWrite,
  registerPatient,
  searchPatients,
} from "./api";
import { registerFormSchema } from "./schemas";

const fetchMock = vi.fn();
const PATIENT = {
  id: "11111111-1111-4111-8111-111111111111",
  full_name: "Test Patient Alpha",
  date_of_birth: "1990-05-17",
  sex: "female",
  phone: "+2348031234567",
  review_status: null,
  duplicate_of_id: null,
};
const OTHER_ID = "22222222-2222-4222-8222-222222222222";
const FORM = {
  full_name: "Test Patient Alpha",
  date_of_birth: "1990-05-17",
  sex: "female" as const,
  phone: null,
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

describe("patients api", () => {
  it("searches with the words safely encoded", async () => {
    fetchMock.mockResolvedValueOnce(answer([PATIENT]));

    expect(await searchPatients("  Ada & Co ")).toEqual([PATIENT]);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/backend/patients?q=Ada%20%26%20Co");
  });

  it("reads one patient", async () => {
    fetchMock.mockResolvedValueOnce(answer(PATIENT));

    expect(await getPatient(PATIENT.id)).toEqual(PATIENT);
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/patients/${PATIENT.id}`);
  });

  it("registers a new patient", async () => {
    fetchMock.mockResolvedValueOnce(answer(PATIENT, 201));

    expect(await registerPatient(FORM)).toEqual({ kind: "registered", patient: PATIENT });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      ...FORM,
      confirmed_not_duplicate: false,
    });
  });

  it("turns the duplicate warning into a question, not an error", async () => {
    fetchMock.mockResolvedValueOnce(
      answer(
        {
          detail: {
            message: "This patient may already be registered.",
            matches: [{ patient_id: OTHER_ID, reason: "same_phone" }],
            hint: "...",
          },
        },
        409,
      ),
    );

    expect(await registerPatient(FORM)).toEqual({
      kind: "possible_duplicate",
      matches: [{ patient_id: OTHER_ID, reason: "same_phone" }],
    });
  });

  it("sends the confirmation when the person says it is someone new", async () => {
    fetchMock.mockResolvedValueOnce(answer(PATIENT, 201));

    await registerPatient(FORM, true);

    expect(JSON.parse(fetchMock.mock.calls[0][1].body).confirmed_not_duplicate).toBe(true);
  });

  it("still fails on a conflict it does not understand", async () => {
    fetchMock.mockResolvedValueOnce(answer({ detail: "Something else." }, 409));

    await expect(registerPatient(FORM)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("registerFormSchema", () => {
  const good = { full_name: "  Ada   Obi ", date_of_birth: "1990-05-17", sex: "female", phone: "  " };

  it("tidies the form and treats an empty phone as none", () => {
    expect(registerFormSchema.parse(good)).toEqual({
      full_name: "Ada   Obi",
      date_of_birth: "1990-05-17",
      sex: "female",
      phone: null,
    });
  });

  it.each([
    [{ full_name: "  " }],
    [{ date_of_birth: "" }],
    [{ date_of_birth: "1899-12-31" }],
    [{ date_of_birth: "2999-01-01" }],
    [{ sex: "" }],
    [{ phone: "0".repeat(41) }],
  ])("refuses %j", (change) => {
    expect(registerFormSchema.safeParse({ ...good, ...change }).success).toBe(false);
  });
});

describe("offline registration and review", () => {
  it("queues an offline registration with its own ID and the offline flag", () => {
    const first = offlineRegistrationWrite(FORM);
    const second = offlineRegistrationWrite(FORM);

    expect(first).toMatchObject({
      path: "/patients",
      body: { ...FORM, registered_offline: true },
      label: "Patient registration",
      encounterId: null,
    });
    expect((first.body as { id: string }).id).not.toBe((second.body as { id: string }).id);
    expect(first.label).not.toContain(FORM.full_name); // the label never carries the name
  });

  it("reads the review list, and treats an older patient answer as not flagged", async () => {
    const { review_status: _status, duplicate_of_id: _of, ...older } = PATIENT;
    const flagged = { ...PATIENT, id: OTHER_ID, review_status: "needs_review" };
    fetchMock.mockResolvedValueOnce(
      answer([{ patient: flagged, matches: [{ patient: older, reason: "same_phone" }] }]),
    );

    const [item] = await getReviewQueue();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/backend/patients/review-queue");
    expect(item.patient.review_status).toBe("needs_review");
    expect(item.matches[0].patient.review_status).toBeNull();
  });

  it("sends the decision", async () => {
    fetchMock.mockResolvedValueOnce(answer({ ...PATIENT, review_status: "duplicate" }));

    await decideReview(OTHER_ID, { decision: "duplicate", duplicate_of: PATIENT.id });

    expect(fetchMock.mock.calls[0][0]).toBe(`/api/backend/patients/${OTHER_ID}/review`);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      decision: "duplicate",
      duplicate_of: PATIENT.id,
    });
  });
});
