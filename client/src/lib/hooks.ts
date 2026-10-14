import { useEffect, useRef, useState, type RefObject } from "react";

/** Calls `onClose` on a click outside `ref` or on Escape, while `open` is true. */
export function useDismiss(ref: RefObject<HTMLElement | null>, open: boolean, onClose: () => void) {
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close.current();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close.current();
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, ref]);
}

export function useMediaQuery(query: string): boolean {
  const [match, setMatch] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const on = () => setMatch(mql.matches);
    mql.addEventListener("change", on);
    return () => mql.removeEventListener("change", on);
  }, [query]);
  return match;
}

/** A localStorage-backed state for per-browser preferences. */
export function useStoredState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? { ...initial, ...JSON.parse(raw) } : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* not critical */
    }
  }, [key, value]);
  return [value, setValue] as const;
}

/**
 * Calls `onVisible` when `ref` scrolls into view (within `rootMargin`), while
 * `enabled`. Re-arms whenever `enabled` turns back on, so a marker that's
 * still visible after a page loads triggers the next page too.
 */
export function useWhenVisible(
  ref: RefObject<HTMLElement | null>,
  enabled: boolean,
  onVisible: () => void,
  rootMargin = "0px",
) {
  const callback = useRef(onVisible);
  callback.current = onVisible;

  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled) return;
    const io = new IntersectionObserver(([entry]) => entry.isIntersecting && callback.current(), { rootMargin });
    io.observe(el);
    return () => io.disconnect();
  }, [ref, enabled, rootMargin]);
}
