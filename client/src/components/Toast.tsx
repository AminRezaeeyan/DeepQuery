import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CircleAlert, CircleCheck, X } from "lucide-react";

type Tone = "error" | "success" | "info";
type Toast = { id: number; tone: Tone; text: string };

const ToastContext = createContext<((text: string, tone?: Tone) => void) | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const push = useCallback(
    (text: string, tone: Tone = "error") => {
      const id = Date.now() + Math.random();
      setToasts((t) => (t.some((x) => x.text === text) ? t : [...t.slice(-2), { id, tone, text }]));
      window.setTimeout(() => dismiss(id), tone === "error" ? 6000 : 3500);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.tone}`}>
            {t.tone === "error" ? <CircleAlert size={16} /> : <CircleCheck size={16} />}
            <span>{t.text}</span>
            <button className="icon-btn icon-btn--sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
