import { describe, expect, it } from "vitest";
import { splitAnswer } from "./format";

describe("splitAnswer", () => {
  it("reads page and sheet locations from references", () => {
    const { body, references } = splitAnswer(
      "ReFinED is 61x faster [1].\n\n**References:**\n[1] refined.pdf, p. 6\n[2] runs.xlsx, sheet: gpu_prices\n[3] https://en.wikipedia.org/wiki/Fandom\n[4] notes.md\n",
    );

    expect(body).toBe("ReFinED is 61x faster [1].");
    expect(references.map((r) => [r.name, r.location, r.url])).toEqual([
      ["refined.pdf", "p. 6", null],
      ["runs.xlsx", "sheet: gpu_prices", null],
      ["https://en.wikipedia.org/wiki/Fandom", null, "https://en.wikipedia.org/wiki/Fandom"],
      ["notes.md", null, null],
    ]);
  });
});
