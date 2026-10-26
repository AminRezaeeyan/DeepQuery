import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { Tokens } from "./types";

type Profile = { email: string; firstName: string; lastName: string };

type AuthState = {
  isAuthed: boolean;
  profile: Profile | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; first_name: string; last_name: string }) => Promise<void>;
  googleLogin: (credential: string) => Promise<void>;
  logout: () => void;
};

const PROFILE_KEY = "dq-profile";
const AuthContext = createContext<AuthState | null>(null);

// The API has no "current user" endpoint, so the profile is what the user
// typed when signing in, kept locally for display only.
function loadProfile(): Profile | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as Profile) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthed, setAuthed] = useState(() => Boolean(tokenStore.get()));
  const [profile, setProfile] = useState<Profile | null>(loadProfile);

  const finish = useCallback((tokens: Tokens, next: Profile | null) => {
    tokenStore.set(tokens);
    if (next) {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(next));
      setProfile(next);
    }
    setAuthed(true);
  }, []);

  const logout = useCallback(() => {
    tokenStore.clear();
    localStorage.removeItem(PROFILE_KEY);
    setProfile(null);
    setAuthed(false);
  }, []);

  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  const value = useMemo<AuthState>(
    () => ({
      isAuthed,
      profile,
      logout,
      login: async (email, password) => {
        const { tokens } = await api.login(email, password);
        const known = loadProfile();
        finish(tokens, known?.email === email ? known : { email, firstName: "", lastName: "" });
      },
      register: async (data) => {
        const { tokens } = await api.register(data);
        finish(tokens, { email: data.email, firstName: data.first_name, lastName: data.last_name });
      },
      googleLogin: async (credential) => {
        const { tokens } = await api.googleLogin(credential);
        finish(tokens, null);
      },
    }),
    [isAuthed, profile, logout, finish],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
