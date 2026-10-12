import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, Globe, Paperclip, SlidersHorizontal, Square, X } from "lucide-react";
import { useDismiss } from "../../lib/hooks";
import type { Audience, Depth, ResearchOptions } from "../../lib/types";

type Props = {
  options: ResearchOptions;
  setOptions: (o: ResearchOptions) => void;
  busy: boolean;
  canAttachImage: boolean;
  image: File | null;
  setImage: (f: File | null) => void;
  onPickFiles: (files: File[]) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  accept: string;
  focusKey: string | undefined;
  prefill: string | null;
  onPrefillUsed: () => void;
};

const DEPTHS: { value: Depth; label: string; hint: string }[] = [
  { value: "Low", label: "Brief", hint: "A few sentences" },
  { value: "Medium", label: "Balanced", hint: "Clear and complete" },
  { value: "High", label: "Deep", hint: "Multi-section analysis" },
];

const AUDIENCES: { value: Audience; label: string }[] = [
  { value: "General", label: "General" },
  { value: "Expert", label: "Expert" },
];

function Switch({ on, onChange, label, hint }: { on: boolean; onChange: (v: boolean) => void; label: string; hint: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} className="switch-row" onClick={() => onChange(!on)}>
      <span className="switch-text">
        <span>{label}</span>
        <small>{hint}</small>
      </span>
      <span className={`switch ${on ? "is-on" : ""}`} />
    </button>
  );
}

function TunePopover({ options, setOptions }: { options: ResearchOptions; setOptions: (o: ResearchOptions) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, open, () => setOpen(false));
  const set = <K extends keyof ResearchOptions>(k: K, v: ResearchOptions[K]) => setOptions({ ...options, [k]: v });

  const changed =
    Number(options.depth !== "Medium") + Number(options.audience !== "General") + Number(options.strictQuotes) + Number(options.challenge);

  return (
    <div className="popover-anchor" ref={ref}>
      <button type="button" className={`chip ${open ? "is-open" : ""}`} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <SlidersHorizontal size={14} />
        <span className="chip-label">{DEPTHS.find((d) => d.value === options.depth)!.label}</span>
        {changed > 0 && <span className="chip-count">{changed}</span>}
      </button>

      {open && (
        <div className="popover popover--up tune" role="dialog" aria-label="Answer settings">
          <div className="tune-group">
            <span className="mono-label">Depth</span>
            <div className="segmented segmented--full">
              {DEPTHS.map((d) => (
                <button key={d.value} className={options.depth === d.value ? "is-on" : ""} onClick={() => set("depth", d.value)} title={d.hint}>
                  {d.label}
                </button>
              ))}
            </div>
          </div>
          <div className="tune-group">
            <span className="mono-label">Written for</span>
            <div className="segmented segmented--full">
              {AUDIENCES.map((a) => (
                <button key={a.value} className={options.audience === a.value ? "is-on" : ""} onClick={() => set("audience", a.value)}>
                  {a.label}
                </button>
              ))}
            </div>
          </div>
          <div className="tune-switches">
            <Switch on={options.strictQuotes} onChange={(v) => set("strictQuotes", v)} label="Strict quotes" hint="Back each major claim with a verbatim quote" />
            <Switch on={options.challenge} onChange={(v) => set("challenge", v)} label="Challenge" hint="Point out gaps, bias and missing views" />
          </div>
        </div>
      )}
    </div>
  );
}

export function Composer(p: Props) {
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);

  useLayoutEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [text]);

  useEffect(() => {
    if (window.matchMedia("(pointer: fine)").matches) ta.current?.focus();
  }, [p.focusKey]);

  const { prefill, onPrefillUsed } = p;
  useEffect(() => {
    if (prefill == null) return;
    setText(prefill);
    onPrefillUsed();
    ta.current?.focus();
  }, [prefill, onPrefillUsed]);

  useEffect(() => {
    if (!p.image) return setPreview(null);
    const url = URL.createObjectURL(p.image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [p.image]);

  const canSend = !p.busy && (text.trim().length > 0 || p.image != null);

  const submit = () => {
    if (!canSend) return;
    p.onSend(text.trim());
    setText("");
  };

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        onPaste={(e) => {
          const img = Array.from(e.clipboardData.files).find((f) => f.type.startsWith("image/"));
          if (img && p.canAttachImage) {
            e.preventDefault();
            p.setImage(img);
          }
        }}
      >
        {preview && (
          <div className="composer-attach">
            <div className="thumb">
              <img src={preview} alt="Attached image" />
              <button type="button" className="thumb-x" onClick={() => p.setImage(null)} aria-label="Remove image">
                <X size={12} />
              </button>
            </div>
          </div>
        )}

        <textarea
          ref={ta}
          className="composer-input"
          dir="auto"
          rows={1}
          value={text}
          placeholder="Ask a question, or paste something to check…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          aria-label="Message"
        />

        <div className="composer-bar">
          <div className="composer-tools">
            <button type="button" className="icon-btn" onClick={() => fileInput.current?.click()} title="Attach documents or an image" aria-label="Attach files">
              <Paperclip size={17} />
            </button>
            <input
              ref={fileInput}
              type="file"
              hidden
              multiple
              accept={p.accept}
              onChange={(e) => {
                p.onPickFiles(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
            />
            <button
              type="button"
              className={`chip ${p.options.webSearch ? "is-active" : ""}`}
              aria-pressed={p.options.webSearch}
              onClick={() => p.setOptions({ ...p.options, webSearch: !p.options.webSearch })}
              title="Search the web before answering"
            >
              <Globe size={14} />
              <span className="chip-label">Web</span>
            </button>
            <TunePopover options={p.options} setOptions={p.setOptions} />
          </div>

          {p.busy ? (
            <button type="button" className="send send--stop" onClick={p.onStop} aria-label="Stop generating" title="Stop (Esc)">
              <Square size={12} fill="currentColor" />
            </button>
          ) : (
            <button type="submit" className="send" disabled={!canSend} aria-label="Send">
              <ArrowUp size={18} strokeWidth={2.4} />
            </button>
          )}
        </div>
      </form>
      <p className="composer-foot">
        Answers cite their sources — open them before you rely on a claim. <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line.
      </p>
    </div>
  );
}
