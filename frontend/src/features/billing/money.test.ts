import { describe, expect, it } from "vitest";

import { formatNaira, nairaInput, parseNaira } from "./money";

describe("formatNaira", () => {
  it("shows kobo as naira with two decimals", () => {
    expect(formatNaira(500_000)).toBe("₦5,000.00");
    expect(formatNaira(123_456_789)).toBe("₦1,234,567.89");
    expect(formatNaira(5)).toBe("₦0.05");
    expect(formatNaira(0)).toBe("₦0.00");
    expect(formatNaira(-150)).toBe("-₦1.50");
  });
});

describe("parseNaira", () => {
  it.each([
    ["5000", 500_000],
    ["5,000", 500_000],
    ["₦5,000.50", 500_050],
    ["5000.5", 500_050],
    [" 5 000 ", 500_000],
    ["0.29", 29],
    ["NGN 1,234,567.89", 123_456_789],
  ])("reads %s as %i kobo", (typed, kobo) => {
    expect(parseNaira(typed)).toBe(kobo);
  });

  it.each(["", "abc", "-5", "5.001", "5,00", "1e3", "5..0"])("refuses %s", (typed) => {
    expect(parseNaira(typed)).toBeNull();
  });
});

describe("nairaInput", () => {
  it("puts kobo back in a box as plain naira", () => {
    expect(nairaInput(500_050)).toBe("5000.50");
    expect(nairaInput(5)).toBe("0.05");
  });
});
