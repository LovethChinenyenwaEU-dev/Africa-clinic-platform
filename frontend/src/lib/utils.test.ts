import { describe, expect, it } from "vitest";

import { cn } from "./utils";

describe("cn", () => {
  it("joins classes and drops empty ones", () => {
    expect(cn("a", false, undefined, "b")).toBe("a b");
  });

  it("lets a later Tailwind class win over a clashing earlier one", () => {
    expect(cn("px-4 text-ink", "px-6")).toBe("text-ink px-6");
  });
});
