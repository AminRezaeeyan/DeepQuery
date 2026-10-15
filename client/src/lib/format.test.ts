import { describe, expect, it } from "vitest";
import { citedReferences, groupSources, splitAnswer } from "./format";

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

describe("citedReferences", () => {
  it("keeps only the references the answer cites, with their numbers", () => {
    const { body, references } = splitAnswer(
      "Fast [3] and accurate [7][3].\n\n**References:**\n" + Array.from({ length: 12 }, (_, i) => `[${i + 1}] refined.pdf, p. ${i + 1}`).join("\n"),
    );

    expect(citedReferences(body, references).map((r) => [r.id, r.location])).toEqual([
      [3, "p. 3"],
      [7, "p. 7"],
    ]);
  });
});

describe("groupSources", () => {
  it("shows each file once with all its citation numbers", () => {
    const { references } = splitAnswer(
      "x\n\n**References:**\n[1] refined.pdf, p. 6\n[2] blink.pdf, p. 7\n[3] refined.pdf, p. 7\n[4] https://en.wikipedia.org/wiki/Fandom\n",
    );

    expect(groupSources(references)).toEqual([
      { name: "refined.pdf", url: null, ids: [1, 3] },
      { name: "blink.pdf", url: null, ids: [2] },
      { name: "https://en.wikipedia.org/wiki/Fandom", url: "https://en.wikipedia.org/wiki/Fandom", ids: [4] },
    ]);
  });
});

describe("sources consulted", () => {
  it("lists what an answer read when it cites nothing", () => {
    const { body, references, consulted } = splitAnswer(
      "It was 159.29 USD over budget.\n\n**Sources consulted:**\n[1] lab_notes.md\n[2] runs.xlsx, sheet: runs\n",
    );

    expect(body).toBe("It was 159.29 USD over budget.");
    expect(consulted).toBe(true);
    expect(references.map((r) => [r.id, r.name, r.location])).toEqual([
      [1, "lab_notes.md", null],
      [2, "runs.xlsx", "sheet: runs"],
    ]);
  });

  it("is off for ordinary references", () => {
    expect(splitAnswer("Fast [1].\n\n**References:**\n[1] refined.pdf, p. 6\n").consulted).toBe(false);
  });
});
