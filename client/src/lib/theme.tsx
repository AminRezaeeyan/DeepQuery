import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemePref = "system" | "light" | "dark";

const KEY = "dq-theme";
const ThemeContext = createContext<{ pref: ThemePref; setPref: (p: ThemePref) => void } | null>(null);

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPref] = useState<ThemePref>(readPref);

  useEffect(() => {
    const root = document.documentElement;
    if (pref === "system") delete root.dataset.theme;
    else root.dataset.theme = pref;
    try {
      if (pref === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, pref);
    } catch {
      /* storage unavailable: theme still applies for this session */
    }
  }, [pref]);

  return <ThemeContext.Provider value={{ pref, setPref }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
