import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Chat, Doc } from "../../lib/types";

export const DOC_EXTENSIONS = [".txt", ".pdf", ".csv", ".xlsx", ".md", ".json", ".py", ".js", ".ts", ".java", ".c", ".cpp"];
export const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp"];

export type UIDoc = Doc & { uploading?: boolean };

const isBusy = (d: UIDoc) => d.uploading || d.status === "pending" || d.status === "processing";

/** Documents attached to one chat, polled while any are still being indexed. */
export function useDocuments(chatId: string | undefined, ensureChat: () => Promise<Chat>, onError: (m: string) => void) {
  const [docs, setDocs] = useState<UIDoc[]>([]);

  const refresh = useCallback(async () => {
    if (!chatId) return setDocs([]);
    const all = await api.documents();
    setDocs((current) => [...all.filter((d) => d.chat === chatId), ...current.filter((d) => d.uploading)]);
  }, [chatId]);

  useEffect(() => {
    // Keep uploads that started before this chat's route was opened.
    setDocs((d) => d.filter((x) => x.uploading && x.chat === chatId));
    refresh().catch(() => undefined);
  }, [refresh]);

  const indexing = docs.some((d) => !d.uploading && isBusy(d));
  useEffect(() => {
    if (!indexing) return;
    const t = window.setInterval(() => refresh().catch(() => undefined), 2500);
    return () => window.clearInterval(t);
  }, [indexing, refresh]);

  const upload = useCallback(
    async (files: File[]) => {
      let chat: Chat;
      try {
        chat = await ensureChat();
      } catch (e) {
        return onError((e as Error).message);
      }
      await Promise.all(
        files.map(async (file) => {
          const temp: UIDoc = {
            uuid: `up-${file.name}-${Date.now()}`,
            chat: chat.uuid,
            file: null,
            original_filename: file.name,
            status: "pending",
            created_at: new Date().toISOString(),
            uploading: true,
          };
          setDocs((d) => [...d, temp]);
          try {
            const doc = await api.uploadDocument(chat.uuid, file);
            setDocs((d) => d.map((x) => (x.uuid === temp.uuid ? doc : x)));
          } catch (e) {
            setDocs((d) => d.filter((x) => x.uuid !== temp.uuid));
            onError(`${file.name}: ${(e as Error).message}`);
          }
        }),
      );
    },
    [ensureChat, onError],
  );

  const remove = useCallback(
    async (uuid: string) => {
      const before = docs;
      setDocs((d) => d.filter((x) => x.uuid !== uuid));
      try {
        await api.deleteDocument(uuid);
      } catch (e) {
        setDocs(before);
        onError((e as Error).message);
      }
    },
    [docs, onError],
  );

  return { docs, upload, remove, indexing: docs.some(isBusy) };
}
