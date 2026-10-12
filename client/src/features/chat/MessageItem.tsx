import { useRef, useState } from "react";
import { Check, Copy, FileText, Globe, Pencil, RotateCcw } from "lucide-react";
import { Markdown } from "../../components/Markdown";
import { hostOf, splitAnswer, timeOf, type Reference } from "../../lib/format";
import type { UIMessage } from "./useChatSession";

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="msg-action"
      onClick={() =>
        navigator.clipboard.writeText(text).then(() => {
          setDone(true);
          window.setTimeout(() => setDone(false), 1400);
        })
      }
    >
      {done ? <Check size={14} /> : <Copy size={14} />}
      <span>{done ? "Copied" : "Copy"}</span>
    </button>
  );
}

function Sources({ refs, flashId }: { refs: Reference[]; flashId: number | null }) {
  return (
    <section className="sources" aria-label="Sources">
      <h4 className="mono-label">Sources</h4>
      <ol>
        {refs.map((r) => {
          const inner = (
            <>
              <span className="src-num">{r.id}</span>
              {r.url ? <Globe size={14} className="src-icon" /> : <FileText size={14} className="src-icon" />}
              <span className="src-name">{r.url ? hostOf(r.url) : r.label}</span>
              {r.url && <span className="src-path">{r.url.replace(/^https?:\/\/(www\.)?[^/]+/, "") || "/"}</span>}
            </>
          );
          return (
            <li key={r.id} className={flashId === r.id ? "is-flash" : ""} data-ref={r.id}>
              {r.url ? (
                <a href={r.url} target="_blank" rel="noreferrer noopener">
                  {inner}
                </a>
              ) : (
                <div>{inner}</div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function AssistantMessage({ message, status, onRetry }: { message: UIMessage; status: string; onRetry?: () => void }) {
  const { body, references } = splitAnswer(message.content);
  const [flash, setFlash] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const showSource = (id: number) => {
    ref.current?.querySelector(`[data-ref="${id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    setFlash(id);
    window.setTimeout(() => setFlash(null), 1600);
  };

  const waiting = message.streaming && !message.content;

  return (
    <article className="msg msg--assistant" ref={ref}>
      <div className="msg-gutter" aria-hidden="true">
        <span className={`msg-pip ${message.streaming ? "is-live" : ""}`} />
      </div>
      <div className="msg-main">
        {waiting ? (
          <div className="thinking">
            <span className="thinking-bar" />
            <span>{status}</span>
          </div>
        ) : (
          <div className={`prose ${message.streaming ? "is-streaming" : ""}`} dir="auto">
            <Markdown text={body} references={references} onCite={showSource} />
          </div>
        )}

        {!message.streaming && references.length > 0 && <Sources refs={references} flashId={flash} />}

        {message.stopped && <p className="msg-note">Stopped. This partial answer isn’t saved to the chat.</p>}

        {!message.streaming && message.content && (
          <div className="msg-actions">
            <CopyButton text={body} />
            {onRetry && (
              <button className="msg-action" onClick={onRetry}>
                <RotateCcw size={14} />
                <span>Retry</span>
              </button>
            )}
            <span className="msg-time">{timeOf(message.created_at)}</span>
          </div>
        )}
      </div>
    </article>
  );
}

function UserMessage({ message, onEdit }: { message: UIMessage; onEdit?: (text: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const image = message.localImage ?? message.image;
  const [imageOk, setImageOk] = useState(true);

  if (editing && onEdit) {
    const save = () => {
      const t = draft.trim();
      if (t && t !== message.content) onEdit(t);
      setEditing(false);
    };
    return (
      <article className="msg msg--user">
        <div className="msg-edit">
          <textarea
            className="input"
            dir="auto"
            value={draft}
            autoFocus
            rows={Math.min(8, draft.split("\n").length + 1)}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                save();
              }
              if (e.key === "Escape") setEditing(false);
            }}
          />
          <div className="msg-edit-bar">
            <span className="hint">The answer below will be replaced.</span>
            <button className="btn btn--ghost btn--sm" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button className="btn btn--primary btn--sm" onClick={save}>
              Save &amp; ask
            </button>
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="msg msg--user">
      <div className="bubble">
        {image && imageOk && <img src={image} alt="" className="bubble-img" onError={() => setImageOk(false)} />}
        {message.content && (
          <p dir="auto" className="bubble-text">
            {message.content}
          </p>
        )}
      </div>
      {onEdit && (
        <div className="msg-actions msg-actions--user">
          <button
            className="msg-action"
            onClick={() => {
              setDraft(message.content);
              setEditing(true);
            }}
          >
            <Pencil size={13} />
            <span>Edit</span>
          </button>
        </div>
      )}
    </article>
  );
}

type Props = {
  message: UIMessage;
  status: string;
  onEdit?: (text: string) => void;
  onRetry?: () => void;
};

export function MessageItem({ message, status, onEdit, onRetry }: Props) {
  return message.role === "user" ? (
    <UserMessage message={message} onEdit={onEdit} />
  ) : (
    <AssistantMessage message={message} status={status} onRetry={onRetry} />
  );
}
