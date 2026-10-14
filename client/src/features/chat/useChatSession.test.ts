import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Chat, ResearchOptions } from "../../lib/types";
import { useChatSession } from "./useChatSession";

const { api } = vi.hoisted(() => ({
  api: { messages: vi.fn(), sendMessage: vi.fn(), editMessage: vi.fn() },
}));

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api };
});

const OPTIONS: ResearchOptions = { webSearch: false, strictQuotes: false, challenge: false, depth: "Medium", audience: "General" };
const CHAT: Chat = {
  uuid: "new-chat",
  provider_id: 1,
  title: "New chat",
  is_temporary: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

/** A streamed response that the test finishes by calling `finish`. */
function controllableStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({ start: (c) => (controller = c) });
  return {
    response: new Response(body),
    finish: (text: string) => {
      controller.enqueue(new TextEncoder().encode(JSON.stringify({ type: "text", text }) + "\n"));
      controller.close();
    },
  };
}

afterEach(() => vi.clearAllMocks());

describe("useChatSession", () => {
  it("keeps streaming the first message when the route moves to the new chat", async () => {
    const stream = controllableStream();
    let signal: AbortSignal | undefined;
    api.sendMessage.mockImplementation((_chat, _text, _opts, _image, s: AbortSignal) => {
      signal = s;
      return Promise.resolve(stream.response);
    });
    api.messages.mockResolvedValue({ next: null, previous: null, results: [] });

    const deps = { ensureChat: async () => CHAT, onChatTouched: vi.fn(), onError: vi.fn() };
    const { result, rerender } = renderHook((props: { chatId?: string }) => useChatSession({ ...deps, chatId: props.chatId }), {
      initialProps: { chatId: undefined as string | undefined },
    });

    let sending!: Promise<void>;
    act(() => {
      sending = result.current.send("What is in this image?", OPTIONS, null);
    });
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalled());

    // Sending created the chat, so the app navigates to it mid-stream.
    rerender({ chatId: CHAT.uuid });

    expect(signal?.aborted).toBe(false);

    await act(async () => {
      stream.finish("It shows a chart.");
      await sending;
    });
    expect(deps.onError).not.toHaveBeenCalled();
    expect(deps.onChatTouched).toHaveBeenCalledWith(CHAT.uuid, true);
  });

  it("stops the answer when the user leaves for another chat", async () => {
    const stream = controllableStream();
    let signal: AbortSignal | undefined;
    api.sendMessage.mockImplementation((_chat, _text, _opts, _image, s: AbortSignal) => {
      signal = s;
      return Promise.resolve(stream.response);
    });
    api.messages.mockResolvedValue({ next: null, previous: null, results: [] });

    const deps = { ensureChat: async () => CHAT, onChatTouched: vi.fn(), onError: vi.fn() };
    const { result, rerender } = renderHook((props: { chatId?: string }) => useChatSession({ ...deps, chatId: props.chatId }), {
      initialProps: { chatId: CHAT.uuid as string | undefined },
    });

    act(() => {
      void result.current.send("Question", OPTIONS, null);
    });
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalled());

    rerender({ chatId: "another-chat" });

    expect(signal?.aborted).toBe(true);
  });
});

describe("failed answers", () => {
  const deps = () => ({ ensureChat: async () => CHAT, onChatTouched: vi.fn(), onError: vi.fn() });
  const saved = { uuid: "q1", role: "user" as const, content: "Question", image: null, created_at: "2026-01-01T00:00:00Z" };

  it("stay in the chat with the error, and retry regenerates a saved question", async () => {
    api.sendMessage.mockResolvedValue(
      new Response(JSON.stringify({ type: "text", text: "Partial " }) + "\n" + JSON.stringify({ type: "error", detail: "The model stopped." }) + "\n"),
    );
    api.messages.mockResolvedValue({ next: null, previous: null, results: [saved] });
    api.editMessage.mockResolvedValue(new Response(JSON.stringify({ type: "text", text: "Fresh answer" }) + "\n"));
    const d = deps();
    const { result } = renderHook(() => useChatSession({ ...d, chatId: CHAT.uuid }));
    await waitFor(() => expect(result.current.loading).toBe(false)); // the chat has loaded before the user sends

    await act(() => result.current.send("Question", OPTIONS, null));

    const failed = result.current.messages.at(-1)!;
    expect(failed.error).toBe("The model stopped.");
    expect(failed.content).toBe("Partial ");
    expect(result.current.messages.map((m) => m.uuid).slice(0, -1)).toEqual(["q1"]);
    expect(d.onError).not.toHaveBeenCalled();

    await act(() => result.current.retry(failed));

    expect(api.editMessage).toHaveBeenCalledWith("q1", "Question", OPTIONS, expect.anything());
    expect(api.sendMessage).toHaveBeenCalledTimes(1);
  });

  it("resend a question the server rejected before saving it", async () => {
    const { ApiError } = await import("../../lib/api");
    api.sendMessage.mockRejectedValueOnce(new ApiError(400, "You have reached your daily message limit (20)."));
    api.messages.mockResolvedValue({ next: null, previous: null, results: [] });
    const d = deps(); // created once: a new onError per render would re-run the load effect forever
    const { result } = renderHook(() => useChatSession({ ...d, chatId: CHAT.uuid }));
    await waitFor(() => expect(result.current.loading).toBe(false)); // the chat has loaded before the user sends

    await act(() => result.current.send("Question", OPTIONS, null));

    const failed = result.current.messages.at(-1)!;
    expect(failed.error).toContain("daily message limit");
    expect(result.current.messages.map((m) => m.role)).toEqual(["user", "assistant"]);

    api.sendMessage.mockResolvedValue(new Response(JSON.stringify({ type: "text", text: "Answer" }) + "\n"));
    await act(() => result.current.retry(failed));

    expect(api.sendMessage).toHaveBeenCalledTimes(2);
    expect(api.editMessage).not.toHaveBeenCalled();
  });
});

describe("research steps", () => {
  it("update in place as a step goes from running to done", async () => {
    const lines = [
      { type: "step", id: 1, tool: "search_documents", status: "running", summary: 'Searching documents for "speed"' },
      { type: "step", id: 1, tool: "search_documents", status: "done", summary: 'Searched documents for "speed" · 6 passages' },
      { type: "text", text: "Answer [1]." },
    ];
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    api.sendMessage.mockImplementation(async () => {
      const body = new ReadableStream<Uint8Array>({
        async start(c) {
          lines.forEach((l) => c.enqueue(new TextEncoder().encode(JSON.stringify(l) + "\n")));
          await gate; // keep the stream open so the live message can be inspected
          c.close();
        },
      });
      return new Response(body);
    });
    api.messages.mockResolvedValue({ next: null, previous: null, results: [] });
    const d = { ensureChat: async () => CHAT, onChatTouched: vi.fn(), onError: vi.fn() };
    const { result } = renderHook(() => useChatSession({ ...d, chatId: CHAT.uuid }));
    await waitFor(() => expect(result.current.loading).toBe(false));

    let sending!: Promise<void>;
    act(() => {
      sending = result.current.send("Question", OPTIONS, null);
    });
    await waitFor(() => expect(result.current.messages.at(-1)?.content).toBe("Answer [1]."));

    expect(result.current.messages.at(-1)?.trace).toEqual([lines[1]]);
    await act(async () => {
      release();
      await sending;
    });
  });
});
