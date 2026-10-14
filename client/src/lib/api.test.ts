import { describe, expect, it, vi } from "vitest";
import { api, ApiError, readStream } from "./api";

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

const line = (event: object) => JSON.stringify(event) + "\n";

describe("readStream", () => {
  it("joins text events, even when lines are split across network chunks", async () => {
    const seen: string[] = [];
    const body = line({ type: "text", text: "Hel" }) + line({ type: "text", text: "lo" });

    const full = await readStream(streamOf(body.slice(0, 10), body.slice(10)), { onText: (t) => seen.push(t) });

    expect(full).toBe("Hello");
    expect(seen.at(-1)).toBe("Hello");
  });

  it("drops a preamble on reset and reports steps", async () => {
    const steps: unknown[] = [];
    const full = await readStream(
      streamOf(
        line({ type: "text", text: "Let me look." }),
        line({ type: "reset" }),
        line({ type: "step", id: 1, tool: "read_document", status: "running", summary: "Reading refined.pdf, p. 6" }),
        line({ type: "step", id: 1, tool: "read_document", status: "done", summary: "Read refined.pdf, p. 6" }),
        line({ type: "text", text: "ReFinED takes 15 s [1]." }),
      ),
      { onText: () => undefined, onStep: (s) => steps.push(s.status) },
    );

    expect(full).toBe("ReFinED takes 15 s [1].");
    expect(steps).toEqual(["running", "done"]);
  });

  it("turns an error event into an ApiError and keeps the partial text", async () => {
    const seen: string[] = [];
    const error = await readStream(streamOf(line({ type: "text", text: "Partial " }), line({ type: "error", detail: "The model stopped." })), {
      onText: (t) => seen.push(t),
    }).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("The model stopped.");
    expect(seen.at(-1)).toBe("Partial ");
  });
});

describe("editMessage", () => {
  it("sends the answer options along with the new text", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("ok"));
    vi.stubGlobal("fetch", fetchMock);
    const opts = { webSearch: true, strictQuotes: true, challenge: false, depth: "High", audience: "Expert" } as const;

    await api.editMessage("m1", "new question", opts, new AbortController().signal);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/messages/m1/");
    expect(JSON.parse(init.body)).toEqual({
      content: "new question",
      enable_web_search: true,
      strict_quote_mode: true,
      challenge_mode: false,
      reasoning_depth: "High",
      audience_type: "Expert",
    });
    vi.unstubAllGlobals();
  });
});

describe("searchChats", () => {
  it("reads a page and follows the next link on the same origin", async () => {
    const fetchMock = vi.fn(async (_url: string) => Response.json({ next: "http://127.0.0.1:8000/api/chats/search/?cursor=abc&q=solar", previous: null, results: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const page = await api.searchChats("solar power");
    await api.searchChats("solar power", page.next);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/chats/search/?q=solar%20power");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/chats/search/?cursor=abc&q=solar");
    vi.unstubAllGlobals();
  });
});
