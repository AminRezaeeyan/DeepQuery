import type {
  AgentStep,
  Chat,
  Doc,
  Message,
  Model,
  Page,
  Plan,
  ResearchOptions,
  Subscription,
  Tokens,
} from "./types";

// Empty means same origin: Vite proxies /api and /auth to Django in dev.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const TOKEN_KEY = "dq-access";
const REFRESH_KEY = "dq-refresh";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (t: Partial<Tokens>) => {
    if (t.access) localStorage.setItem(TOKEN_KEY, t.access);
    if (t.refresh) localStorage.setItem(REFRESH_KEY, t.refresh);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

/** Flattens DRF error bodies ({"detail"}, ["msg"], {"field": ["msg"]}) into one line. */
function errorMessage(body: unknown, fallback: string): string {
  if (!body) return fallback;
  if (typeof body === "string") return body;
  if (Array.isArray(body)) return body.map((b) => errorMessage(b, "")).filter(Boolean).join(" ");
  if (typeof body === "object") {
    const obj = body as Record<string, unknown>;
    if (typeof obj.detail === "string") return obj.detail;
    const parts = Object.entries(obj).map(([key, value]) => {
      const msg = errorMessage(value, "");
      return key === "non_field_errors" ? msg : `${key.replace(/_/g, " ")}: ${msg}`;
    });
    return parts.filter(Boolean).join(" ") || fallback;
  }
  return fallback;
}

/** Turns DRF's absolute pagination links into same-origin paths. */
function toPath(url: string): string {
  try {
    const u = new URL(url, window.location.origin);
    return u.pathname + u.search;
  } catch {
    return url;
  }
}

// One refresh at a time: parallel 401s all wait for the same attempt.
let refreshing: Promise<boolean> | null = null;

function refreshAccess(): Promise<boolean> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return Promise.resolve(false);
  refreshing ??= fetch(API_BASE + "/auth/token/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  })
    .then(async (res) => {
      if (!res.ok) return false;
      tokenStore.set((await res.json()) as Partial<Tokens>);
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const res = await fetch(API_BASE + path, { ...init, headers });

  if (res.status === 401 && token) {
    // The access token lasts an hour; trade the refresh token for a new one and retry once.
    if (retry && (await refreshAccess())) return request(path, init, false);
    tokenStore.clear();
    onUnauthorized();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, errorMessage(body, `Request failed (${res.status})`));
  }
  return res;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await request(path, init);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const body = (data: unknown) => JSON.stringify(data);

/** The API's names for the answer settings, shared by send and edit. */
export const answerOptions = (opts: ResearchOptions) => ({
  enable_web_search: opts.webSearch,
  strict_quote_mode: opts.strictQuotes,
  challenge_mode: opts.challenge,
  reasoning_depth: opts.depth,
  audience_type: opts.audience,
});

export const api = {
  login: (email: string, password: string) =>
    json<{ tokens: Tokens }>("/auth/login/", { method: "POST", body: body({ email, password }) }),

  register: (data: { email: string; password: string; first_name: string; last_name: string }) =>
    json<{ tokens: Tokens }>("/auth/register/", { method: "POST", body: body(data) }),

  googleLogin: (token: string) =>
    json<{ tokens: Tokens }>("/auth/google/", { method: "POST", body: body({ token }) }),

  chats: (next?: string | null) => json<Page<Chat>>(next ? toPath(next) : "/api/chats/"),

  searchChats: (q: string, next?: string | null) =>
    json<Page<Chat>>(next ? toPath(next) : `/api/chats/search/?q=${encodeURIComponent(q)}`),

  chat: (uuid: string) => json<Chat>(`/api/chats/${uuid}/`),

  createChat: () => json<Chat>("/api/chats/", { method: "POST", body: body({}) }),

  updateChat: (uuid: string, data: Partial<Pick<Chat, "title" | "provider_id" | "is_temporary">>) =>
    json<Chat>(`/api/chats/${uuid}/`, { method: "PATCH", body: body(data) }),

  deleteChat: (uuid: string) => json<void>(`/api/chats/${uuid}/`, { method: "DELETE" }),

  messages: (uuid: string, next?: string | null) =>
    json<Page<Message>>(next ? toPath(next) : `/api/chats/${uuid}/messages/`),

  models: () => json<Model[]>("/api/models/"),

  /** Loads a private file (e.g. a chat image) with the user's token. */
  blob: async (path: string) => (await request(path)).blob(),

  documents: () => json<Doc[]>("/api/documents/"),

  uploadDocument: (chat: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("chat", chat);
    return json<Doc>("/api/documents/", { method: "POST", body: form });
  },

  deleteDocument: (uuid: string) => json<void>(`/api/documents/${uuid}/`, { method: "DELETE" }),

  plans: () => json<Plan[]>("/api/subscriptions/plans/"),

  subscription: () => json<Subscription>("/api/subscriptions/my-subscription/"),

  startPayment: (planId: number) =>
    json<{ payment_url: string; authority: string }>("/api/subscriptions/payment/initiate/", {
      method: "POST",
      body: body({ plan_id: planId }),
    }),

  /** Confirms a ZarinPal payment from the parameters it adds to the return URL. */
  verifyPayment: (authority: string, status: string) =>
    json<{ message: string; ref_id: string; plan: string }>(
      `/api/subscriptions/payment/verify/?Authority=${encodeURIComponent(authority)}&Status=${encodeURIComponent(status)}`,
    ),

  /** Sends a message and returns the streamed plain-text answer. */
  sendMessage: (chat: string, content: string, opts: ResearchOptions, image: File | null, signal: AbortSignal) => {
    const form = new FormData();
    form.append("content", content);
    for (const [key, value] of Object.entries(answerOptions(opts))) form.append(key, String(value));
    if (image) form.append("image", image);
    return request(`/api/chats/${chat}/messages/`, { method: "POST", body: form, signal });
  },

  /** Replaces the last user message and streams a fresh answer with the given options. */
  editMessage: (uuid: string, content: string, opts: ResearchOptions, signal: AbortSignal) =>
    request(`/api/messages/${uuid}/`, { method: "PATCH", body: body({ content, ...answerOptions(opts) }), signal }),
};

type StreamEvent =
  | { type: "text"; text: string }
  | { type: "reset" }
  | ({ type: "step" } & AgentStep)
  | { type: "error"; detail?: string };

type StreamHandlers = {
  onText: (full: string) => void;
  onStep?: (step: AgentStep) => void;
};

/**
 * Reads an answer stream: JSON lines of events (see chats/services/chat_service.py).
 * Text accumulates, "reset" drops a preamble the agent wrote before using tools,
 * steps go to onStep, and an error event throws, keeping the text so far.
 */
export async function readStream(res: Response, handlers: StreamHandlers): Promise<string> {
  if (!res.body) return "";
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  const handle = (line: string) => {
    if (!line.trim()) return;
    let event: StreamEvent;
    try {
      event = JSON.parse(line) as StreamEvent;
    } catch {
      return; // a malformed line shouldn't lose the whole answer
    }
    if (event.type === "text") {
      full += event.text;
      handlers.onText(full);
    } else if (event.type === "reset") {
      full = "";
      handlers.onText(full);
    } else if (event.type === "step") {
      handlers.onStep?.(event);
    } else if (event.type === "error") {
      throw new ApiError(502, event.detail || "The answer stopped before it finished. Try again.");
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(handle);
  }
  handle(buffer + decoder.decode());
  return full;
}
