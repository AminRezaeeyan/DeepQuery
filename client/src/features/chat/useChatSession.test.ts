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
      controller.enqueue(new TextEncoder().encode(text));
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
