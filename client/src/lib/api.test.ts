import { describe, expect, it } from "vitest";
import { ApiError, readStream } from "./api";

function streamOf(...chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((c) => controller.enqueue(encoder.encode(c)));
        controller.close();
      },
    }),
  );
}

describe("readStream", () => {
  it("returns the full answer", async () => {
    const seen: string[] = [];
    expect(await readStream(streamOf("Hel", "lo"), (t) => seen.push(t))).toBe("Hello");
    expect(seen.at(-1)).toBe("Hello");
  });

  it("turns a mid-stream error into an ApiError and keeps the partial text", async () => {
    const seen: string[] = [];
    const error = await readStream(streamOf("Partial ", '\u001e{"detail": "The model stopped."}'), (t) => seen.push(t)).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("The model stopped.");
    expect(seen.at(-1)).toBe("Partial ");
  });

  it("never shows the marker even when it arrives split from its JSON", async () => {
    const seen: string[] = [];
    await readStream(streamOf("Partial \u001e", '{"detail": "x"}'), (t) => seen.push(t)).catch(() => undefined);

    expect(seen.every((t) => !t.includes("\u001e"))).toBe(true);
  });
});
