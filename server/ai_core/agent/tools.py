"""
The research agent's tools. Each tool declares a JSON-schema signature for the
model and returns text for the model plus a one-line summary for the UI.
Sources a tool returns are registered for citation and shown as [n] (label).
"""
import re
from dataclasses import dataclass, field
from urllib.parse import quote

import requests

from ai_core.services.embedding_service import EmbeddingService
from ai_core.services.web_search_service import UnsafeURL, WebPageFetcher, WebSearchService, check_public_url
from documents.models import Document

from .citations import SourceRegistry

TOOL_REGISTRY = {}
MAX_OUTPUT_CHARS = 12000
HTTP_TIMEOUT = 10
WIKIPEDIA_HEADERS = {"User-Agent": "DeepQuery/0.1 (research assistant)"}


@dataclass
class ToolContext:
    chat_id: int
    user_id: int
    sources: SourceRegistry = field(default_factory=SourceRegistry)


@dataclass
class ToolOutput:
    text: str      # what the model reads
    summary: str   # one line for the UI, e.g. 'Read refined.pdf, p. 6'


def register_tool(cls):
    TOOL_REGISTRY[cls.name] = cls
    return cls


def tool_definitions() -> list[dict]:
    return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in TOOL_REGISTRY.values()]


def run_tool(name: str, arguments: dict, context: ToolContext) -> ToolOutput:
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return ToolOutput(f"Unknown tool '{name}'. Available: {', '.join(TOOL_REGISTRY)}.", f"Unknown tool {name}")
    try:
        output = tool().run(context, **arguments)
    except TypeError as e:  # wrong or missing arguments from the model
        return ToolOutput(f"Wrong arguments for {name}: {e}", f"{name} failed")
    if len(output.text) > MAX_OUTPUT_CHARS:
        output.text = output.text[:MAX_OUTPUT_CHARS] + "\n[... cut to keep the context small; narrow the request to see more]"
    return output


def chat_documents(context: ToolContext):
    # Document.chat points at the chat's uuid, so filter through the relation, not chat_id.
    return Document.objects.filter(chat__id=context.chat_id, user_id=context.user_id, source_type=Document.SourceTypeChoices.FILE)


def relevant_windows(text: str, query: str, size: int = 1500, top: int = 3) -> str:
    """The parts of a long text that share the most words with the query, in reading order."""
    windows = [text[i:i + size] for i in range(0, len(text), size)]
    words = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 2}
    if not words or len(windows) <= top:
        return text[: size * top]
    scored = sorted(range(len(windows)), key=lambda i: -sum(windows[i].lower().count(w) for w in words))[:top]
    return "\n...\n".join(windows[i] for i in sorted(scored))


@register_tool
class SearchDocuments:
    name = "search_documents"
    description = (
        "Search the documents attached to this chat for passages relevant to a query. "
        "Returns numbered passages with their file and page. Use specific terms (names, metrics, table names)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for."},
            "limit": {"type": "integer", "description": "How many passages (1-10).", "default": 6},
        },
        "required": ["query"],
    }

    def run(self, context, query, limit=6):
        if not chat_documents(context).exists():
            return ToolOutput("No documents are attached to this chat.", f'Searched documents for "{query}" (none attached)')
        results = EmbeddingService().search(query, content_model=Document, limit=max(1, min(int(limit), 10)), tag=f"chat:{context.chat_id}")
        parts = []
        for doc, score, text, location in results:
            n = context.sources.add(("doc", doc.id, location), filename=doc.original_filename, url=doc.source_url, location=location)
            parts.append(f"[{n}] ({context.sources.label(n)})\n{text.strip()}")
        if not parts:
            return ToolOutput("No passages matched.", f'Searched documents for "{query}" · nothing found')
        return ToolOutput("\n\n".join(parts), f'Searched documents for "{query}" · {len(parts)} passages')


@register_tool
class ReadDocument:
    name = "read_document"
    description = (
        "Read an attached document exactly: a PDF page or page range (e.g. '6' or '5-7'), or a spreadsheet "
        "sheet by name. Use it to read tables and numbers precisely after search_documents finds where they are. "
        "Without 'part', returns short documents whole and lists the pages or sheets of long ones."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The document's file name, e.g. 'refined.pdf'."},
            "part": {"type": "string", "description": "Page ('6'), page range ('5-7') or sheet name. Optional."},
        },
        "required": ["name"],
    }

    def run(self, context, name, part=None):
        docs = list(chat_documents(context))
        doc = next((d for d in docs if (d.original_filename or "").lower() == name.lower()), None) or next(
            (d for d in docs if name.lower() in (d.original_filename or "").lower()), None
        )
        if not doc:
            available = ", ".join(d.original_filename for d in docs) or "none"
            return ToolOutput(f"No document named '{name}'. Attached documents: {available}.", f"Looked for {name}")

        segments = doc.extracted_segments or [{"label": None, "text": doc.extracted_text}]
        selected = self._select(segments, part)
        if selected is None:
            labels = ", ".join(s["label"] for s in segments if s["label"])
            if len(doc.extracted_text) <= MAX_OUTPUT_CHARS:
                selected = segments
            else:
                return ToolOutput(
                    f"{doc.original_filename} is long; read it in parts. Parts: {labels}.",
                    f"Listed the parts of {doc.original_filename}",
                )

        parts = []
        for seg in selected:
            n = context.sources.add(("doc", doc.id, seg["label"] or ""), filename=doc.original_filename, location=seg["label"] or "")
            parts.append(f"[{n}] ({context.sources.label(n)})\n{seg['text'].strip()}")
        where = ", ".join(s["label"] for s in selected if s["label"])
        return ToolOutput("\n\n".join(parts), f"Read {doc.original_filename}" + (f", {where}" if where and len(selected) <= 3 else ""))

    @staticmethod
    def _select(segments, part):
        if not part:
            return None
        part = str(part).strip().lower().removeprefix("p.").removeprefix("page").strip()
        pages = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", part)
        if pages:
            first, last = int(pages.group(1)), int(pages.group(2) or pages.group(1))
            wanted = {f"p. {n}" for n in range(first, min(last, first + 4) + 1)}  # at most 5 pages at once
            return [s for s in segments if s["label"] in wanted] or None
        return [s for s in segments if s["label"] and part in s["label"].lower()] or None


@register_tool
class WebSearch:
    name = "web_search"
    description = "Search the web. Returns numbered results with title, URL and a snippet. Follow up with fetch_page to read a result."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search query."}},
        "required": ["query"],
    }

    def run(self, context, query):
        results = WebSearchService().search(query, max_results=5)
        if not results:
            return ToolOutput("The web search returned no results.", f'Searched the web for "{query}" · no results')
        parts = []
        for r in results:
            n = context.sources.add(("url", r["url"]), url=r["url"])
            parts.append(f"[{n}] {r['title']}\n{r['url']}\n{r['snippet'] or ''}")
        return ToolOutput("\n\n".join(parts), f'Searched the web for "{query}" · {len(parts)} results')


@register_tool
class FetchPage:
    name = "fetch_page"
    description = (
        "Read a web page (public http/https only). With 'query', returns the parts of the page most "
        "relevant to it instead of the beginning."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "query": {"type": "string", "description": "What to find on the page. Optional."},
        },
        "required": ["url"],
    }

    def run(self, context, url, query=None):
        text = WebPageFetcher().fetch(url)
        if not text:
            return ToolOutput(f"Couldn't read {url} (unreachable, not public, or not a text page).", f"Couldn't read {url}")
        n = context.sources.add(("url", url), url=url)
        body = relevant_windows(text, query) if query else text[:6000]
        return ToolOutput(f"[{n}] ({url})\n{body}", f"Read {url}")


@register_tool
class Wikipedia:
    name = "wikipedia"
    description = "Look up a topic on Wikipedia and return the most relevant parts of the best-matching article."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "language": {"type": "string", "description": "Wikipedia language code, e.g. 'en' or 'fa'.", "default": "en"},
        },
        "required": ["query"],
    }

    def run(self, context, query, language="en"):
        # The language becomes part of the host name, so allow only a plain code.
        if not re.fullmatch(r"[a-z]{2,3}", language or ""):
            return ToolOutput("The language must be a Wikipedia code like 'en' or 'fa'.", "Wikipedia lookup failed")
        api = f"https://{language}.wikipedia.org/w/api.php"
        try:
            check_public_url(api)
            hits = requests.get(api, params={"action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json"},
                                headers=WIKIPEDIA_HEADERS, timeout=HTTP_TIMEOUT).json()["query"]["search"]
            if not hits:
                return ToolOutput(f"Wikipedia ({language}) has no article for '{query}'.", f'Searched Wikipedia for "{query}" · nothing found')
            title = hits[0]["title"]
            pages = requests.get(api, params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": title, "format": "json"},
                                 headers=WIKIPEDIA_HEADERS, timeout=HTTP_TIMEOUT).json()["query"]["pages"]
        except (requests.RequestException, KeyError, ValueError, UnsafeURL) as e:
            return ToolOutput(f"Wikipedia lookup failed: {e}", "Wikipedia lookup failed")
        extract = next(iter(pages.values())).get("extract", "")
        url = f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        n = context.sources.add(("url", url), url=url)
        return ToolOutput(f"[{n}] Wikipedia: {title} ({url})\n{relevant_windows(extract, query)}", f"Read Wikipedia: {title}")
