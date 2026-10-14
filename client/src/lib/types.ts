export type Tokens = { access: string; refresh: string; token_type?: string };

export type Chat = {
  uuid: string;
  provider_id: number | null;
  title: string;
  is_temporary: boolean;
  created_at: string;
  updated_at: string;
};

export type Role = "user" | "assistant" | "system";

/** One research step of the agent: a tool it ran and what came of it. */
export type AgentStep = {
  id?: number;
  tool: string;
  arguments?: Record<string, unknown>;
  status?: "running" | "done";
  summary: string;
};

export type Message = {
  uuid: string;
  role: Role;
  content: string;
  image: string | null;
  created_at: string;
  /** The agent's research steps, for assistant messages. */
  trace?: AgentStep[];
};

export type Page<T> = { next: string | null; previous: string | null; results: T[] };

export type Model = {
  id: number;
  name: string;
  provider_type: string;
  model_name: string;
  description: string | null;
  supports_vision: boolean;
  is_default_for_chat: boolean;
};

export type DocumentStatus = "pending" | "processing" | "done" | "failed";

export type Doc = {
  uuid: string;
  chat: string;
  file: string | null;
  original_filename: string | null;
  status: DocumentStatus;
  created_at: string;
};

export type Plan = {
  id: number;
  name: string;
  price: number;
  daily_message_limit: number;
  daily_document_limit: number;
  daily_image_limit: number;
};

export type Subscription = {
  id: number;
  plan: Plan;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
};

export type Depth = "Low" | "Medium" | "High";
export type Audience = "General" | "Expert";

export type ResearchOptions = {
  webSearch: boolean;
  strictQuotes: boolean;
  challenge: boolean;
  depth: Depth;
  audience: Audience;
};
