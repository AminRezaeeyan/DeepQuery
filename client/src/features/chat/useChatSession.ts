import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, readStream } from "../../lib/api";
import type { Chat, Message, ResearchOptions } from "../../lib/types";

/** What was asked, kept on a failed answer so it can be retried. */
type AnswerRequest = { content: string; opts: ResearchOptions; image: File | null };

export type UIMessage = Message & {
  streaming?: boolean;
  stopped?: boolean;
  localImage?: string;
  /** Set on an answer that failed; shown in the chat with a Retry button. */
  error?: string;
  /** The question behind a failed answer, and whether the server saved it. */
  failedRequest?: AnswerRequest & { saved: boolean };
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
    async (
      uuid: string,
      assistantId: string,
      start: (signal: AbortSignal) => Promise<Response>,
      firstMessage: boolean,
      request: AnswerRequest,
    ) => {
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
          // Show the failure where the answer would have been. Re-sync first
          // to learn whether the server saved the question, which decides how
          // Retry works (regenerate it, or send it again).
          const error = e instanceof ApiError ? e.message : "The answer could not be generated.";
          const synced = await fetchLatest(uuid).catch(() => null);
          setMessages((current) => {
            const local = current.filter((x) => x.uuid.startsWith("local-") && x.uuid !== assistantId);
            const last = synced?.list.at(-1);
            const saved = Boolean(last && last.role === "user" && last.content === request.content);
            const failed: UIMessage = {
              uuid: assistantId,
              role: "assistant",
              content: streamed,
              image: null,
              created_at: new Date().toISOString(),
              error,
              failedRequest: { ...request, saved },
            };
            if (!synced) return current.map((x) => (x.uuid === assistantId ? failed : x));
            return [...synced.list, ...(saved ? [] : local), failed];
          });
          if (synced) setOlderCursor(synced.next);
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

      await consume(chat.uuid, assistantId, (signal) => api.sendMessage(chat.uuid, content, opts, image, signal), firstMessage, {
        content,
        opts,
        image,
      });
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
      await consume(chatId, assistantId, (signal) => api.editMessage(message.uuid, content, opts, signal), false, {
        content,
        opts,
        image: null,
      });
    },
    [busy, chatId, consume],
  );

  /** Tries a failed answer again without duplicating the question. */
  const retry = useCallback(
    async (failed: UIMessage) => {
      const request = failed.failedRequest;
      if (busy || !request) return;
      if (request.saved) {
        const question = [...messages].reverse().find((m) => m.role === "user");
        if (question) await edit(question, request.content, request.opts);
        return;
      }
      // The server never stored the question: drop the local copy and send it again.
      setMessages((m) => m.filter((x) => !x.uuid.startsWith("local-")));
      await send(request.content, request.opts, request.image);
    },
    [busy, edit, messages, send],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { messages, loading, loadingOlder, hasOlder: Boolean(olderCursor), loadOlder, send, edit, retry, stop, busy };
}
