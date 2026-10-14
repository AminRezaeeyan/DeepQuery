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
from ai_core.services.web_search_service import UnsafeURL, WebPageFetcher, WebSearchService, check_public_url, html_to_text
from documents.models import Document

from .citations import SourceRegistry
from .sandbox import run_python, sandbox_mode

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


WEB_TOOLS = {"web_search", "fetch_page", "wikipedia"}


def tool_definitions(web: bool = True) -> list[dict]:
    """The tools offered to the model; web tools only when the user turned web search on."""
    return [
        {"name": t.name, "description": t.description, "parameters": t.parameters}
        for t in TOOL_REGISTRY.values()
        if (web or t.name not in WEB_TOOLS) and (t.name != "run_python" or sandbox_mode() != "off")
    ]


def describe_call(name: str, arguments: dict) -> str:
    """What the agent is doing, for the UI while a tool runs."""
    tool = TOOL_REGISTRY.get(name)
    try:
        return tool.describe(**arguments) if tool else f"Calling {name}"
    except TypeError:
        return f"Calling {name}"


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

    @staticmethod
    def describe(query="", **_):
        return f'Searching documents for "{query}"'

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

    @staticmethod
    def describe(name="", part=None, **_):
        if part and re.fullmatch(r"\d+(\s*-\s*\d+)?", str(part).strip()):
            part = f"p. {part}"
        return f"Reading {name}" + (f", {part}" if part else "")

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

    @staticmethod
    def describe(query="", **_):
        return f'Searching the web for "{query}"'

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

    @staticmethod
    def describe(url="", **_):
        return f"Reading {url}"

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
    description = (
        "Read a Wikipedia article, with its tables and lists. Returns the intro, the list of sections, "
        "and the section matching your query (or the one you name in 'section'). Pass 'as_of' (a year "
        "or YYYY-MM-DD) to read the article as it was then, e.g. when a question names a version."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The article or topic, e.g. 'Mercedes Sosa discography'."},
            "section": {"type": "string", "description": "A section title to read, e.g. 'Studio albums'. Optional."},
            "as_of": {"type": "string", "description": "Read the revision from this year or date (YYYY or YYYY-MM-DD). Optional."},
            "language": {"type": "string", "description": "Wikipedia language code, e.g. 'en' or 'fa'.", "default": "en"},
        },
        "required": ["query"],
    }

    @staticmethod
    def describe(query="", as_of=None, **_):
        return f'Looking up "{query}" on Wikipedia' + (f" (as of {as_of})" if as_of else "")

    def run(self, context, query, section=None, as_of=None, language="en"):
        # The language becomes part of the host name, so allow only a plain code.
        if not re.fullmatch(r"[a-z]{2,3}", language or ""):
            return ToolOutput("The language must be a Wikipedia code like 'en' or 'fa'.", "Wikipedia lookup failed")
        if as_of and not re.fullmatch(r"\d{4}(-\d{2}-\d{2})?", str(as_of)):
            return ToolOutput("'as_of' must be a year (2022) or a date (2022-12-31).", "Wikipedia lookup failed")
        api = f"https://{language}.wikipedia.org/w/api.php"
        try:
            check_public_url(api)
            return self._read(context, api, language, query, section, as_of)
        except (requests.RequestException, KeyError, ValueError, UnsafeURL) as e:
            return ToolOutput(f"Wikipedia lookup failed: {e}", "Wikipedia lookup failed")

    def _read(self, context, api, language, query, section, as_of):
        def get(**params):
            return requests.get(api, params={**params, "format": "json"}, headers=WIKIPEDIA_HEADERS, timeout=HTTP_TIMEOUT).json()

        hits = get(action="query", list="search", srsearch=query, srlimit=5)["query"]["search"]
        if not hits:
            return ToolOutput(f"Wikipedia ({language}) has no article for '{query}'.", f'Searched Wikipedia for "{query}" · nothing found')
        title = hits[0]["title"]

        revision_params = {"rvstart": f"{as_of}T23:59:59Z" if len(str(as_of)) == 10 else f"{as_of}-12-31T23:59:59Z", "rvdir": "older"} if as_of else {}
        page = next(iter(get(action="query", prop="revisions", titles=title, rvlimit=1, rvprop="ids|timestamp", **revision_params)["query"]["pages"].values()))
        if not page.get("revisions"):
            return ToolOutput(f"'{title}' has no revision from {as_of} or earlier.", f"Wikipedia: no {as_of} revision of {title}")
        revision = page["revisions"][0]
        sections = get(action="parse", oldid=revision["revid"], prop="sections")["parse"]["sections"]

        wanted = self._pick_section(sections, section, query)
        parts = [self._section_text(get, revision["revid"], "0")]
        if wanted:
            parts.append(self._section_text(get, revision["revid"], wanted["index"]))  # includes its heading

        url = (
            f"https://{language}.wikipedia.org/w/index.php?oldid={revision['revid']}" if as_of
            else f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        )
        n = context.sources.add(("url", url), url=url)
        header = f"[{n}] Wikipedia: {title} (revision of {revision['timestamp'][:10]}) {url}"
        others = ", ".join(h["title"] for h in hits[1:])
        outline = ", ".join(("  " * (int(s["toclevel"]) - 1)) + s["line"] for s in sections)
        body = "\n\n".join(p for p in parts if p)
        text = f"{header}\n" + (f"Other matching articles: {others}\n" if others else "") + f"Sections: {outline}\n\n{body}"
        if section and not wanted:
            text += f"\n\n(No section named '{section}'.)"
        return ToolOutput(text, f"Read Wikipedia: {title}" + (f", {wanted['line']}" if wanted else "") + (f" (as of {as_of})" if as_of else ""))

    @staticmethod
    def _pick_section(sections, section, query):
        if section:
            return next((s for s in sections if s["line"].lower() == section.lower()), None) or next(
                (s for s in sections if section.lower() in s["line"].lower()), None
            )
        words = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 3}
        scored = [(sum(w in s["line"].lower() for w in words), s) for s in sections]
        best = max(scored, key=lambda item: item[0], default=(0, None))
        return best[1] if best[0] else None

    @staticmethod
    def _section_text(get, revid, index):
        html = get(action="parse", oldid=revid, prop="text", section=index)["parse"]["text"]["*"]
        return html_to_text(html)


@register_tool
class RunPython:
    name = "run_python"
    description = (
        "Run Python 3 in a sandbox without network access. The chat's attached files are in the working "
        "directory under their names, and pandas, numpy and openpyxl are installed. Only what you print is "
        "returned. Use it for any arithmetic, counting or statistics (e.g. pd.read_csv / pd.read_excel with "
        "sheet_name=None), and to find out what a script prints: run it with runpy.run_path('script.py'). "
        "For code in other languages, translate it faithfully to Python and run that."
    )
    parameters = {
        "type": "object",
        "properties": {"code": {"type": "string", "description": "The Python program. Print the results you need."}},
        "required": ["code"],
    }

    @staticmethod
    def describe(**_):
        return "Running Python"

    def run(self, context, code):
        docs = [d for d in chat_documents(context) if d.file]
        files, cited = [], []
        for doc in docs:
            try:
                files.append((doc.original_filename, doc.file.path))
            except (ValueError, NotImplementedError):
                continue
            n = context.sources.add(("doc", doc.id, ""), filename=doc.original_filename)
            cited.append(f"[{n}] {doc.original_filename}")

        result = run_python(code, files)
        if result.timed_out:
            status = "stopped: took too long"
        else:
            status = f"exit code {result.exit_code}"
        lines = [f"({status})"]
        if cited:
            lines.append("Files available (cite these when your result comes from them): " + ", ".join(cited))
        lines.append("stdout:\n" + (result.stdout or "(nothing printed)"))
        if result.stderr.strip():
            lines.append("stderr:\n" + result.stderr)
        ok = result.exit_code == 0 and not result.timed_out
        return ToolOutput("\n".join(lines), f"Ran Python ({len(code.splitlines())} lines)" + ("" if ok else f" · {status}"))
