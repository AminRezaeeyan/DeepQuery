import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, readStream } from "../../lib/api";
import type { Chat, Message, ResearchOptions } from "../../lib/types";

export type UIMessage = Message & {
  streaming?: boolean;
  stopped?: boolean;
  localImage?: string;
};

type Deps = {
  chatId: string | undefined;
  ensureChat: () => Promise<Chat>;
  onChatTouched: (uuid: string, firstMessage: boolean) => void;
  onError: (msg: string) => void;
};

const tempId = () => `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

/** Messages of one chat: loading, paging back, sending, streaming, editing. */
export function useChatSession({ chatId, ensureChat, onChatTouched, onError }: Deps) {
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // Set when this hook created the chat itself, so the route change that
  // follows doesn't wipe the messages that are streaming in.
  const adoptedChat = useRef<string | null>(null);

  const fetchLatest = useCallback(async (uuid: string) => {
    const page = await api.messages(uuid);
    return { list: [...page.results].reverse() as UIMessage[], next: page.next };
  }, []);

  useEffect(() => {
    // The route just changed to the chat this hook created for the first
    // message; that message is streaming in now, so leave it alone.
    if (chatId && adoptedChat.current === chatId) {
      adoptedChat.current = null;
      return;
    }
    // Leaving a chat: stop its answer.
    abortRef.current?.abort();
    if (!chatId) {
      setMessages([]);
      setOlderCursor(null);
      return;
    }
    let live = true;
    setLoading(true);
    setMessages([]);
    fetchLatest(chatId)
      .then(({ list, next }) => {
        if (!live) return;
        setMessages(list);
        setOlderCursor(next);
      })
      .catch((e: Error) => live && onError(e.message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [chatId, fetchLatest, onError]);

  const loadOlder = useCallback(async () => {
    if (!chatId || !olderCursor || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const page = await api.messages(chatId, olderCursor);
      setMessages((m) => [...[...page.results].reverse(), ...m]);
      setOlderCursor(page.next);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setLoadingOlder(false);
    }
  }, [chatId, olderCursor, loadingOlder, onError]);

  /** Streams the response of `start` into the assistant message, then re-syncs ids with the server. */
  const consume = useCallback(
    async (uuid: string, assistantId: string, start: (signal: AbortSignal) => Promise<Response>, firstMessage: boolean) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      let streamed = "";
      try {
        const res = await start(controller.signal);
        await readStream(res, (text) => {
          streamed = text;
          setMessages((m) => m.map((x) => (x.uuid === assistantId ? { ...x, content: text } : x)));
        });
        const { list, next } = await fetchLatest(uuid);
        setMessages(list);
        setOlderCursor(next);
        onChatTouched(uuid, firstMessage);
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          // The server saves the question but drops an interrupted answer,
          // so keep the partial text locally on top of the server's list.
          const { list, next } = await fetchLatest(uuid).catch(() => ({ list: null, next: null }));
          if (list) {
            const partial: UIMessage = {
              uuid: assistantId,
              role: "assistant",
              content: streamed,
              image: null,
              created_at: new Date().toISOString(),
              stopped: true,
            };
            setMessages(streamed ? [...list, partial] : list);
            setOlderCursor(next);
          }
          onChatTouched(uuid, firstMessage);
        } else {
          setMessages((m) => m.filter((x) => x.uuid !== assistantId || x.content));
          onError(e instanceof ApiError ? e.message : "The answer could not be generated. Try again.");
        }
      } finally {
        setMessages((m) => m.map((x) => (x.uuid === assistantId ? { ...x, streaming: false } : x)));
        if (abortRef.current === controller) abortRef.current = null;
        setBusy(false);
      }
    },
    [fetchLatest, onChatTouched, onError],
  );

  const send = useCallback(
    async (content: string, opts: ResearchOptions, image: File | null) => {
      if (busy) return;
      let chat: Chat;
      try {
        chat = await ensureChat();
      } catch (e) {
        onError((e as Error).message);
        return;
      }
      if (chat.uuid !== chatId) adoptedChat.current = chat.uuid;

      const now = new Date().toISOString();
      const assistantId = tempId();
      const firstMessage = messages.length === 0;
      setMessages((m) => [
        ...(chat.uuid === chatId ? m : []),
        { uuid: tempId(), role: "user", content, image: null, created_at: now, localImage: image ? URL.createObjectURL(image) : undefined },
        { uuid: assistantId, role: "assistant", content: "", image: null, created_at: now, streaming: true },
      ]);

      await consume(chat.uuid, assistantId, (signal) => api.sendMessage(chat.uuid, content, opts, image, signal), firstMessage);
    },
    [busy, chatId, consume, ensureChat, messages.length, onError],
  );

  const edit = useCallback(
    async (message: UIMessage, content: string, opts: ResearchOptions) => {
      if (busy || !chatId) return;
      const assistantId = tempId();
      setMessages((m) => {
        const at = m.findIndex((x) => x.uuid === message.uuid);
        return [
          ...m.slice(0, at),
          { ...message, content },
          { uuid: assistantId, role: "assistant", content: "", image: null, created_at: new Date().toISOString(), streaming: true },
        ];
      });
      await consume(chatId, assistantId, (signal) => api.editMessage(message.uuid, content, opts, signal), false);
    },
    [busy, chatId, consume],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { messages, loading, loadingOlder, hasOlder: Boolean(olderCursor), loadOlder, send, edit, stop, busy };
}
