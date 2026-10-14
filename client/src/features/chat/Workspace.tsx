import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowDown, FileUp } from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { displayTitle } from "../../lib/format";
import { useMediaQuery, useStoredState } from "../../lib/hooks";
import type { Chat, Model, ResearchOptions, Subscription } from "../../lib/types";
import { useToast } from "../../components/Toast";
import { ChatHeader } from "./ChatHeader";
import { Composer } from "./Composer";
import { EmptyState } from "./EmptyState";
import { MessageItem } from "./MessageItem";
import { Sidebar } from "./Sidebar";
import { SourcesPanel } from "./SourcesPanel";
import { useChatSession } from "./useChatSession";
import { DOC_EXTENSIONS, IMAGE_EXTENSIONS, useDocuments } from "./useDocuments";

const DEFAULT_OPTIONS: ResearchOptions = { webSearch: false, strictQuotes: false, challenge: false, depth: "Medium", audience: "General" };
const ACCEPT = [...DOC_EXTENSIONS, ...IMAGE_EXTENSIONS].join(",");
const isImage = (f: File) => IMAGE_EXTENSIONS.some((e) => f.name.toLowerCase().endsWith(e));
const isDoc = (f: File) => DOC_EXTENSIONS.some((e) => f.name.toLowerCase().endsWith(e));

export function Workspace() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { profile } = useAuth();
  const isWide = useMediaQuery("(min-width: 1180px)");

  const [chats, setChats] = useState<Chat[]>([]);
  const [chatsNext, setChatsNext] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Chat[] | null>(null);
  const [resultsNext, setResultsNext] = useState<string | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [current, setCurrent] = useState<Chat | null>(null);
  const [draft, setDraft] = useState<{ modelId: number | null; temporary: boolean }>({ modelId: null, temporary: false });
  const [options, setOptions] = useStoredState<ResearchOptions>("dq-options", DEFAULT_OPTIONS);
  const [image, setImage] = useState<File | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sourcesPref, setSourcesPref] = useStoredState("dq-panels", { sources: true });
  const [sourcesSheet, setSourcesSheet] = useState(false);
  const [prefill, setPrefill] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const creating = useRef<Promise<Chat> | null>(null);

  const onError = useCallback((m: string) => toast(m), [toast]);

  // ----- bootstrap -----
  useEffect(() => {
    api.chats().then((p) => {
      setChats(p.results);
      setChatsNext(p.next);
    }, (e: Error) => onError(e.message));
    api.models().then(setModels, () => undefined);
    api.subscription().then(setSubscription, () => undefined);
  }, [onError]);

  const loadMoreResults = useCallback(() => {
    if (!resultsNext) return;
    const next = resultsNext;
    setResultsNext(null);
    api.searchChats(query, next).then((p) => {
      setResults((r) => [...(r ?? []), ...p.results]);
      setResultsNext(p.next);
    }, () => undefined);
  }, [query, resultsNext]);

  const loadMoreChats = useCallback(() => {
    if (!chatsNext) return;
    const next = chatsNext;
    setChatsNext(null);
    api.chats(next).then((p) => {
      setChats((c) => [...c, ...p.results.filter((x) => !c.some((y) => y.uuid === x.uuid))]);
      setChatsNext(p.next);
    }, () => undefined);
  }, [chatsNext]);

  // ----- search -----
  useEffect(() => {
    const q = query.trim();
    if (!q) return setResults(null);
    const t = window.setTimeout(
      () =>
        api.searchChats(q).then(
          (page) => {
            setResults(page.results);
            setResultsNext(page.next);
          },
          () => setResults([]),
        ),
      220,
    );
    return () => window.clearTimeout(t);
  }, [query]);

  // ----- current chat -----
  useEffect(() => {
    setImage(null);
    if (!chatId) return setCurrent(null);
    const known = chats.find((c) => c.uuid === chatId);
    if (known) return setCurrent(known);
    api.chat(chatId).then(setCurrent, () => {
      onError("That chat doesn’t exist or was deleted.");
      navigate("/", { replace: true });
    });
    // `chats` is only consulted when the route changes, not on every list update.
  }, [chatId]);

  const upsertChat = useCallback((chat: Chat) => {
    // Temporary chats never appear in history, like the server's list.
    setChats((c) => (chat.is_temporary ? c.filter((x) => x.uuid !== chat.uuid) : [chat, ...c.filter((x) => x.uuid !== chat.uuid)]));
    setCurrent((cur) => (cur?.uuid === chat.uuid || !cur ? chat : cur));
  }, []);

  const ensureChat = useCallback(async (): Promise<Chat> => {
    if (chatId && current?.uuid === chatId) return current;
    if (creating.current) return creating.current;
    creating.current = (async () => {
      let chat = await api.createChat();
      const patch: Partial<Chat> = {};
      if (draft.modelId && draft.modelId !== chat.provider_id) patch.provider_id = draft.modelId;
      if (draft.temporary !== chat.is_temporary) patch.is_temporary = draft.temporary;
      if (Object.keys(patch).length) chat = await api.updateChat(chat.uuid, patch);
      upsertChat(chat);
      navigate(`/c/${chat.uuid}`);
      return chat;
    })();
    try {
      return await creating.current;
    } finally {
      creating.current = null;
    }
  }, [chatId, current, draft, navigate, upsertChat]);

  const pollTitle = useCallback(
    (uuid: string, tries = 0) => {
      api.chat(uuid).then((c) => {
        if (/^new chat$/i.test(c.title) && tries < 8) window.setTimeout(() => pollTitle(uuid, tries + 1), 1500);
        else setChats((list) => list.map((x) => (x.uuid === uuid ? c : x)));
        setCurrent((cur) => (cur?.uuid === uuid ? c : cur));
      }, () => undefined);
    },
    [],
  );

  const onChatTouched = useCallback(
    (uuid: string, first: boolean) => {
      api.chat(uuid).then(upsertChat, () => undefined);
      if (first) window.setTimeout(() => pollTitle(uuid), 1200);
      api.subscription().then(setSubscription, () => undefined);
    },
    [pollTitle, upsertChat],
  );

  const session = useChatSession({ chatId, ensureChat, onChatTouched, onError });
  const documents = useDocuments(chatId, ensureChat, onError);
  const { messages, busy, stop } = session;
  const clearPrefill = useCallback(() => setPrefill(null), []);

  // ----- model / temporary -----
  const defaultModel = models.find((m) => m.is_default_for_chat) ?? models[0] ?? null;
  const model = useMemo(() => {
    const id = current ? current.provider_id : draft.modelId;
    return models.find((m) => m.id === id) ?? (current ? null : defaultModel);
  }, [current, draft.modelId, models, defaultModel]);
  const locked = messages.length > 0;
  const temporary = current ? current.is_temporary : draft.temporary;

  const changeModel = async (m: Model) => {
    if (!m.supports_vision) setImage(null);
    if (!current) return setDraft((d) => ({ ...d, modelId: m.id }));
    try {
      upsertChat(await api.updateChat(current.uuid, { provider_id: m.id }));
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const changeTemporary = async (v: boolean) => {
    if (!current) return setDraft((d) => ({ ...d, temporary: v }));
    try {
      upsertChat(await api.updateChat(current.uuid, { is_temporary: v }));
    } catch (e) {
      onError((e as Error).message);
    }
  };

  // ----- chats -----
  const newChat = useCallback(() => {
    stop();
    setDraft({ modelId: null, temporary: false });
    setSidebarOpen(false);
    navigate("/");
  }, [navigate, stop]);

  const renameChat = async (uuid: string, title: string) => {
    try {
      upsertChat(await api.updateChat(uuid, { title }));
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const deleteChat = async (uuid: string) => {
    try {
      await api.deleteChat(uuid);
      setChats((c) => c.filter((x) => x.uuid !== uuid));
      setResults((r) => r && r.filter((x) => x.uuid !== uuid));
      if (uuid === chatId) navigate("/");
    } catch (e) {
      onError((e as Error).message);
    }
  };

  // ----- files -----
  const pickFiles = (files: File[]) => {
    const images = files.filter(isImage);
    const docs = files.filter(isDoc);
    const rejected = files.filter((f) => !isImage(f) && !isDoc(f));
    if (rejected.length) onError(`Not supported: ${rejected.map((f) => f.name).join(", ")}`);
    if (images.length) {
      if (model?.supports_vision) setImage(images[0]);
      else onError(`${model?.name ?? "This model"} can’t read images. Pick a model marked “images”.`);
    }
    if (docs.length) {
      documents.upload(docs);
      if (isWide) setSourcesPref((p) => ({ ...p, sources: true }));
    }
  };

  // ----- keyboard -----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSidebarOpen(true);
        window.setTimeout(() => searchRef.current?.focus(), 0);
      } else if (mod && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        newChat();
      } else if (e.key === "Escape" && busy) {
        stop();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, newChat, stop]);

  // ----- scrolling -----
  const scroller = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);
  const prevHeight = useRef(0);
  const prevFirst = useRef<string | undefined>(undefined);

  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const first = messages[0]?.uuid;
    if (prevFirst.current && first !== prevFirst.current && el.scrollHeight > prevHeight.current && !pinned) {
      // Older messages were prepended: keep the reader's place.
      el.scrollTop += el.scrollHeight - prevHeight.current;
    } else if (pinned) {
      el.scrollTop = el.scrollHeight;
    }
    prevFirst.current = first;
    prevHeight.current = el.scrollHeight;
  }, [messages, pinned]);

  useEffect(() => setPinned(true), [chatId]);

  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  };

  // ----- render helpers -----
  const lastUserIdx = messages.map((m) => m.role).lastIndexOf("user");
  const lastUser = messages[lastUserIdx];
  const canEdit = !busy && lastUser && !lastUser.uuid.startsWith("local-");
  const status = options.webSearch ? "Searching the web and reading sources" : documents.docs.length ? "Reading your sources" : "Thinking";
  const sourcesVisible = isWide ? sourcesPref.sources : sourcesSheet;
  const firstName = profile?.firstName ?? "";

  return (
    <div className={`app ${sidebarOpen ? "sidebar-is-open" : ""} ${sourcesVisible ? "sources-is-open" : ""}`}>
      <Sidebar
        chats={results ?? chats}
        activeId={chatId}
        hasMore={results ? Boolean(resultsNext) : Boolean(chatsNext)}
        onLoadMore={results ? loadMoreResults : loadMoreChats}
        query={query}
        setQuery={setQuery}
        searching={Boolean(query.trim()) && results === null}
        onNew={newChat}
        onRename={renameChat}
        onDelete={deleteChat}
        onClose={() => setSidebarOpen(false)}
        subscription={subscription}
        searchRef={searchRef}
      />
      <div className="scrim scrim--sidebar" onClick={() => setSidebarOpen(false)} />

      <main
        className="main"
        onDragEnter={(e) => {
          if (e.dataTransfer.types.includes("Files")) setDragging(true);
        }}
      >
        <ChatHeader
          title={chatId ? displayTitle(current?.title) : "New research"}
          models={models}
          model={model}
          onModel={changeModel}
          locked={locked}
          temporary={temporary}
          onTemporary={changeTemporary}
          sourceCount={documents.docs.length}
          indexing={documents.indexing}
          sourcesOpen={sourcesVisible}
          onToggleSources={() => (isWide ? setSourcesPref((p) => ({ ...p, sources: !p.sources })) : setSourcesSheet((s) => !s))}
          onMenu={() => setSidebarOpen(true)}
        />

        <div className="thread" ref={scroller} onScroll={onScroll}>
          {session.loading ? (
            <div className="thread-inner">
              <div className="skeleton skeleton--user" />
              <div className="skeleton skeleton--lines" />
            </div>
          ) : messages.length === 0 ? (
            <EmptyState name={firstName} onPick={setPrefill} />
          ) : (
            <div className="thread-inner">
              {session.hasOlder && (
                <button className="load-older" onClick={session.loadOlder} disabled={session.loadingOlder}>
                  {session.loadingOlder ? "Loading…" : "Show earlier messages"}
                </button>
              )}
              {messages.map((m, i) => (
                <MessageItem
                  key={m.uuid}
                  message={m}
                  status={status}
                  onEdit={canEdit && i === lastUserIdx ? (text) => session.edit(m, text, options) : undefined}
                  onRetry={
                    m.error
                      ? busy
                        ? undefined
                        : () => session.retry(m)
                      : canEdit && m.role === "assistant" && i === messages.length - 1 && i > lastUserIdx
                        ? () => session.edit(lastUser, lastUser.content, options)
                        : undefined
                  }
                />
              ))}
            </div>
          )}
        </div>

        {!pinned && messages.length > 0 && (
          <button
            className="jump"
            onClick={() => scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" })}
            aria-label="Jump to latest"
          >
            <ArrowDown size={16} />
          </button>
        )}

        <Composer
          options={options}
          setOptions={setOptions}
          busy={busy}
          canAttachImage={Boolean(model?.supports_vision)}
          image={image}
          setImage={setImage}
          onPickFiles={pickFiles}
          onSend={(text) => {
            session.send(text, options, image);
            setImage(null);
            setPinned(true);
          }}
          onStop={stop}
          accept={ACCEPT}
          focusKey={chatId}
          prefill={prefill}
          onPrefillUsed={clearPrefill}
        />

        {dragging && (
          <div
            className="drop-overlay"
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              pickFiles(Array.from(e.dataTransfer.files));
            }}
          >
            <div className="drop-card">
              <FileUp size={26} />
              <strong>Drop to add sources</strong>
              <span>Documents are indexed for this chat. Images attach to your next message.</span>
            </div>
          </div>
        )}
      </main>

      {sourcesVisible && (
        <>
          <SourcesPanel
            docs={documents.docs}
            onUpload={pickFiles}
            onRemove={documents.remove}
            onClose={() => (isWide ? setSourcesPref((p) => ({ ...p, sources: false })) : setSourcesSheet(false))}
            accept={DOC_EXTENSIONS.join(",")}
          />
          {!isWide && <div className="scrim scrim--sources" onClick={() => setSourcesSheet(false)} />}
        </>
      )}
    </div>
  );
}
