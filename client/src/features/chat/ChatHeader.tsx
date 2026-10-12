import { useRef, useState } from "react";
import { Check, ChevronDown, Eye, EyeOff, Image, Lock, Menu, PanelRight } from "lucide-react";
import { useDismiss } from "../../lib/hooks";
import type { Model } from "../../lib/types";

function ModelPicker({ models, value, onChange, locked }: { models: Model[]; value: Model | null; onChange: (m: Model) => void; locked: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, open, () => setOpen(false));

  return (
    <div className="popover-anchor" ref={ref}>
      <button
        className="model-btn"
        onClick={() => !locked && setOpen((o) => !o)}
        aria-expanded={open}
        aria-disabled={locked}
        title={locked ? "The model can’t change once a chat has messages" : "Choose a model"}
      >
        <span className="model-name">{value?.name ?? "Default model"}</span>
        {locked ? <Lock size={12} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div className="popover menu model-menu" role="listbox">
          <p className="menu-note">Pick before you send — it stays fixed for this chat.</p>
          {models.map((m) => (
            <button
              key={m.id}
              role="option"
              aria-selected={m.id === value?.id}
              className="menu-item model-item"
              onClick={() => {
                onChange(m);
                setOpen(false);
              }}
            >
              <span className="model-item-text">
                <span>
                  {m.name}
                  {m.is_default_for_chat && <em className="tag">default</em>}
                </span>
                <small>
                  {m.provider_type} · {m.model_name}
                  {m.supports_vision && (
                    <>
                      {" · "}
                      <Image size={11} /> images
                    </>
                  )}
                </small>
              </span>
              {m.id === value?.id && <Check size={15} className="accent" />}
            </button>
          ))}
          {!models.length && <p className="menu-note">No chat models are configured yet. Add one in the admin panel.</p>}
        </div>
      )}
    </div>
  );
}

type Props = {
  title: string;
  models: Model[];
  model: Model | null;
  onModel: (m: Model) => void;
  locked: boolean;
  temporary: boolean;
  onTemporary: (v: boolean) => void;
  sourceCount: number;
  indexing: boolean;
  sourcesOpen: boolean;
  onToggleSources: () => void;
  onMenu: () => void;
};

export function ChatHeader(p: Props) {
  return (
    <header className="chat-header">
      <button className="icon-btn menu-btn" onClick={p.onMenu} aria-label="Open sidebar">
        <Menu size={19} />
      </button>

      <div className="chat-header-title">
        <h1 dir="auto">{p.title}</h1>
        {p.temporary && <span className="tag tag--temp">Temporary</span>}
      </div>

      <div className="chat-header-tools">
        <ModelPicker models={p.models} value={p.model} onChange={p.onModel} locked={p.locked} />

        {!p.locked && (
          <button
            className={`icon-btn ${p.temporary ? "is-active" : ""}`}
            onClick={() => p.onTemporary(!p.temporary)}
            aria-pressed={p.temporary}
            title={p.temporary ? "Temporary: not saved to memory" : "Make this a temporary chat"}
            aria-label="Temporary chat"
          >
            {p.temporary ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        )}

        <button
          className={`sources-btn ${p.sourcesOpen ? "is-active" : ""}`}
          onClick={p.onToggleSources}
          aria-pressed={p.sourcesOpen}
          aria-label="Sources"
        >
          <PanelRight size={16} />
          <span className="sources-btn-label">Sources</span>
          {p.sourceCount > 0 && <span className={`count ${p.indexing ? "is-busy" : ""}`}>{p.sourceCount}</span>}
        </button>
      </div>
    </header>
  );
}
