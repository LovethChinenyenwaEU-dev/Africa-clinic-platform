import { describe, expect, it } from "vitest";

import { ageFrom, formatDate, formatDateTime, todayInLagos } from "./format";

describe("formatDate", () => {
  it("shows the exact calendar date, whatever the time zone", () => {
    expect(formatDate("1990-05-17")).toBe("17 May 1990");
    expect(formatDate("2026-01-01")).toBe("1 Jan 2026");
  });

  it("refuses something that is not a date", () => {
    expect(() => formatDate("17/05/1990")).toThrow(RangeError);
  });
});

describe("formatDateTime", () => {
  it("shows server moments in Lagos time", () => {
    // 23:30 UTC on 1 Nov is 00:30 on 2 Nov in Lagos.
    expect(formatDateTime("2026-11-01T23:30:00Z")).toContain("2 Nov 2026");
  });
});

describe("todayInLagos", () => {
  it("uses the Lagos calendar date", () => {
    expect(todayInLagos(new Date("2026-11-01T23:30:00Z"))).toBe("2026-11-02");
  });
});

describe("ageFrom", () => {
  it.each([
    ["1990-05-17", "2026-05-17", "36 years"],
    ["1990-05-17", "2026-05-16", "35 years"],
    ["2025-01-10", "2026-10-14", "21 months"],
    ["2026-09-14", "2026-10-14", "1 month"],
    ["2026-10-13", "2026-10-14", "1 day"],
    ["2026-10-14", "2026-10-14", "0 days"],
  ])("born %s, on %s: %s", (born, today, age) => {
    expect(ageFrom(born, today)).toBe(age);
  });
});
