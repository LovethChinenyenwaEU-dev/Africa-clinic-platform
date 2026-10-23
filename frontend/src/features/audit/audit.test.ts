import { describe, expect, it } from "vitest";

import { NO_FILTERS, auditQuery } from "./api";
import { ACTION_LABELS, describeAction, isRead } from "./labels";

const PATIENT = "11111111-1111-4111-8111-111111111111";
const STAFF = "22222222-2222-4222-8222-222222222222";

function paramsOf(result: ReturnType<typeof auditQuery>) {
  if ("problem" in result) throw new Error(result.problem);
  return Object.fromEntries(new URLSearchParams(result.query));
}

describe("auditQuery", () => {
  it("asks for the largest page and nothing else when there are no filters", () => {
    expect(paramsOf(auditQuery(NO_FILTERS))).toEqual({ limit: "200" });
  });

  it("turns whole Lagos days into a since and an exclusive until", () => {
    const params = paramsOf(
      auditQuery({ ...NO_FILTERS, fromDay: "2026-11-03", toDay: "2026-11-03" }),
    );

    expect(params.since).toBe("2026-11-03T00:00:00+01:00");
    expect(params.until).toBe("2026-11-04T00:00:00+01:00");
  });

  it("rolls the end day over a month and a year", () => {
    expect(paramsOf(auditQuery({ ...NO_FILTERS, toDay: "2026-11-30" })).until).toBe(
      "2026-12-01T00:00:00+01:00",
    );
    expect(paramsOf(auditQuery({ ...NO_FILTERS, toDay: "2026-12-31" })).until).toBe(
      "2027-01-01T00:00:00+01:00",
    );
  });

  it("filters by patient and staff member", () => {
    const params = paramsOf(auditQuery({ ...NO_FILTERS, patientId: ` ${PATIENT} `, staffId: STAFF }));

    expect(params.patient_id).toBe(PATIENT);
    expect(params.staff_id).toBe(STAFF);
  });

  it.each([
    [{ patientId: "Adaeze" }, "A patient ID looks like"],
    [{ fromDay: "2026-11-04", toDay: "2026-11-03" }, "The start day must not be after"],
  ])("explains a filter that makes no sense: %j", (change, problem) => {
    const result = auditQuery({ ...NO_FILTERS, ...change });

    expect("problem" in result && result.problem).toContain(problem);
  });
});

describe("labels", () => {
  it("has plain words for every action the backend writes", () => {
    expect(Object.keys(ACTION_LABELS)).toHaveLength(75);
    expect(describeAction("note.view")).toBe("Viewed notes");
    expect(describeAction("vitals.resolve")).toBe("Settled a vitals conflict");
  });

  it("shows an unknown action as it is rather than hiding it", () => {
    expect(describeAction("something.new")).toBe("something.new");
  });

  it("knows which lines are someone looking", () => {
    expect(isRead("patient.view")).toBe(true);
    expect(isRead("patient.search")).toBe(true);
    expect(isRead("patient.review_list")).toBe(true);
    expect(isRead("patient.review")).toBe(false);
    expect(isRead("note.write")).toBe(false);
  });
});
