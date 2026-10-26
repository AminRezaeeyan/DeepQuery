import type { Chat } from "./types";

export type Reference = { id: number; label: string; url: string | null; name: string; location: string | null };

const REF_MARKER = "**References:**";
// Sent instead when an answer used sources but cites none of them: what the agent read.
const CONSULTED_MARKER = "**Sources consulted:**";

/** Splits a streamed answer into its body and the reference list the server appends. */
export function splitAnswer(text: string): { body: string; references: Reference[]; consulted: boolean } {
  const consultedAt = text.lastIndexOf(CONSULTED_MARKER);
  const consulted = consultedAt !== -1;
  const at = consulted ? consultedAt : text.lastIndexOf(REF_MARKER);
  if (at === -1) return { body: text, references: [], consulted: false };
  const marker = consulted ? CONSULTED_MARKER : REF_MARKER;

  const references: Reference[] = [];
  for (const line of text.slice(at + marker.length).split("\n")) {
    const m = line.trim().match(/^\[(\d+)\]\s+(.+)$/);
    if (!m) continue;
    const label = m[2].trim();
    // "refined.pdf, p. 6" -> name "refined.pdf", location "p. 6";
    // "runs.xlsx (sheets: notes, runs)" -> name "runs.xlsx", location "sheets: notes, runs"
    const place = label.match(/^(.*), (p\. \d+|sheet: .+)$/) ?? label.match(/^(.*) \((sheets: [^)]*)\)$/);
    const name = place ? place[1] : label;
    references.push({
      id: Number(m[1]),
      label,
      name,
      location: place ? place[2] : null,
      url: /^https?:\/\//i.test(name) ? name : null,
    });
  }
  return { body: text.slice(0, at).trimEnd(), references, consulted };
}

/** The references the answer actually cites (older answers listed every retrieved passage). */
export function citedReferences(body: string, references: Reference[]): Reference[] {
  const cited = new Set([...body.matchAll(/\[(\d{1,3})\]/g)].map((m) => Number(m[1])));
  return references.filter((r) => cited.has(r.id));
}

export type SourceGroup = { name: string; url: string | null; ids: number[] };

/** One entry per source file or web page, with every citation number that points into it. */
export function groupSources(references: Reference[]): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  for (const r of references) {
    const key = r.url ?? r.name;
    const group = groups.get(key) ?? { name: r.name, url: r.url, ids: [] };
    group.ids.push(r.id);
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** Turns [1] and [1][2] citations into links the markdown renderer shows as chips. */
export function linkCitations(body: string): string {
  // Leave code spans and fences alone.
  return body
    .split(/(```[\s\S]*?```|`[^`\n]*`)/g)
    .map((part, i) => (i % 2 ? part : part.replace(/\[(\d{1,3})\](?![(:])/g, "[$1](#cite-$1)")))
    .join("");
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

const DAY = 24 * 60 * 60 * 1000;

export function groupChats(chats: Chat[]): { label: string; items: Chat[] }[] {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const t0 = startOfToday.getTime();

  const buckets: [string, (t: number) => boolean][] = [
    ["Today", (t) => t >= t0],
    ["Yesterday", (t) => t >= t0 - DAY],
    ["Previous 7 days", (t) => t >= t0 - 7 * DAY],
    ["Previous 30 days", (t) => t >= t0 - 30 * DAY],
    ["Older", () => true],
  ];

  const groups = new Map<string, Chat[]>();
  for (const chat of chats) {
    const t = new Date(chat.updated_at).getTime();
    const label = buckets.find(([, test]) => test(t))![0];
    groups.set(label, [...(groups.get(label) ?? []), chat]);
  }
  return buckets.filter(([l]) => groups.has(l)).map(([label]) => ({ label, items: groups.get(label)! }));
}

export function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function extOf(name: string | null): string {
  const m = (name ?? "").match(/\.([a-z0-9]+)$/i);
  return m ? m[1].toLowerCase() : "";
}

export function displayTitle(title: string | null | undefined): string {
  const t = (title ?? "").trim();
  return !t || /^new chat$/i.test(t) ? "Untitled research" : t;
}
