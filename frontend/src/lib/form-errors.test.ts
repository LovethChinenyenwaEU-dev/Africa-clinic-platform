import { describe, expect, it } from "vitest";
import { z } from "zod";

import { errorsByField } from "./form-errors";

const schema = z.object({
  name: z.string().min(1, "Enter a name.").max(3, "Too long."),
  age: z.number({ message: "Enter an age." }),
});

describe("errorsByField", () => {
  it("keeps the first message for each listed field", () => {
    const result = schema.safeParse({ name: "", age: "x" });
    if (result.success) throw new Error("expected a failure");

    expect(errorsByField(result.error, ["name", "age"])).toEqual({
      name: "Enter a name.",
      age: "Enter an age.",
    });
  });

  it("ignores fields it was not asked about", () => {
    const result = schema.safeParse({ name: "", age: 1 });
    if (result.success) throw new Error("expected a failure");

    expect(errorsByField(result.error, ["age"])).toEqual({});
  });
});
