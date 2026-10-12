import ipaddress
import logging
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from django.conf import settings

from ai_core.services.llm_service import LLMService
from documents.models import Document
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

URL_REGEX = r"(https?://[^\s]+)"

def extract_urls(text: str):
    return re.findall(URL_REGEX, text)



class WebSearchQueryGenerator:
    SYSTEM_PROMPT = (
        "Generate a concise web search query.\n"
        "Rules:\n"
        "- Maximum 12 words\n"
        "- Focus on keywords\n"
        "- No quotes\n"
        "- No punctuation\n"
        "- Optimize for search engines"
    )

    def __init__(self):
        self.llm = LLMService(task_type="web_query_generation")

    def generate(self, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        stream = self.llm.stream(messages=messages)

        query = ""

        for token in stream:
            query += str(token)
        return query.strip()
    


class UnsafeURL(Exception):
    pass


def check_public_url(url: str) -> None:
    """
    Raises UnsafeURL unless url is http(s) and its host resolves only to
    public addresses. Stops prompts from making the server fetch internal
    services, cloud metadata endpoints or localhost.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURL(f"Only http and https URLs can be fetched: {url}")

    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise UnsafeURL(f"Could not resolve {parsed.hostname}")

    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if address.version == 6 and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global:
            raise UnsafeURL(f"{parsed.hostname} resolves to a non-public address")


class WebPageFetcher:
    MAX_REDIRECTS = 3
    MAX_BYTES = 2_000_000
    TIMEOUT = (5, 10)
    ALLOWED_TYPES = ("text/html", "text/plain", "application/xhtml+xml")

    def fetch(self, url: str) -> str:
        try:
            res = self._get(url)
            html = self._read_limited(res)
        except (UnsafeURL, requests.RequestException) as e:
            logger.info("Skipped %s: %s", url, e)
            return ""

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text)

        return text[:20000]

    def _get(self, url: str):
        # Redirects are followed by hand so every hop is checked.
        for _ in range(self.MAX_REDIRECTS + 1):
            check_public_url(url)
            res = requests.get(url, timeout=self.TIMEOUT, allow_redirects=False, stream=True)
            if res.is_redirect:
                url = urljoin(url, res.headers["Location"])
                res.close()
                continue
            res.raise_for_status()
            content_type = res.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type and content_type not in self.ALLOWED_TYPES:
                res.close()
                raise UnsafeURL(f"Unsupported content type {content_type}")
            return res
        raise UnsafeURL("Too many redirects")

    def _read_limited(self, res) -> str:
        chunks, size = [], 0
        for chunk in res.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > self.MAX_BYTES:
                break
            chunks.append(chunk)
        res.close()
        return b"".join(chunks).decode(res.encoding or "utf-8", errors="replace")

class SerperProvider:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://google.serper.dev/search"

    def search(self, query: str):
        payload = {"q": f"{query}"} 
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        response = requests.post(self.url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        results = []

        for item in data.get("organic", [])[:5]:
            results.append({
                "title": item.get("title"),
                "url": item.get("link"),
                "snippet": item.get("snippet"),
            })
        return results

class WebSearchService:
    def __init__(self):
        api_key = getattr(settings, "SERPER_API_KEY", None)
        if not api_key:
            raise ValueError("SERPER_API_KEY is not set.")
        self.provider = SerperProvider(api_key)

    def search(self, query: str):
        try:
            return self.provider.search(query)
        except Exception as e:
            logger.warning("Web search failed: %s", e)
            return []



class WebKnowledgeService:
    SCORE_THRESHOLD = 0.5
    MAX_SEARCH_RESULTS = 3

    def __init__(self, chat, user):
        self.fetcher = WebPageFetcher()
        self.query_generator = WebSearchQueryGenerator()
        self.search_service = WebSearchService()
        self.embedding_service = EmbeddingService()
        self.chat = chat
        self.user = user

    def gather_and_embed(self, prompt: str) -> None:
        """Fetches, cleans, saves to DB, and embeds web pages."""

        # Cap how many pages one prompt can make the server fetch.
        urls_to_process = extract_urls(prompt)[:self.MAX_SEARCH_RESULTS]

        # If no explicit URLs, generate query and search
        if not urls_to_process:
            query = self.query_generator.generate(prompt)
            results = self.search_service.search(query)
            urls_to_process = [r["url"] for r in results[:self.MAX_SEARCH_RESULTS]]

        for url in urls_to_process:
            page_text = self.fetcher.fetch(url)

            logger.info("Fetched %d chars from %s", len(page_text), url)
            if not page_text:
                continue

            from chats.models import Chat  # Import here to avoid circular import issuee
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user_instance = User.objects.get(id=self.user)
            chat_instance = Chat.objects.get(id=self.chat)
                
            # Create the document instance
            doc = Document.objects.create(
                chat=chat_instance,
                user=user_instance,
                source_type="web",
                source_url=url,
                extracted_text=page_text
            )
            
            # Embed using the instance and a chat-specific tag
            self.embedding_service.embed_instance(
                instance=doc, 
                text=page_text, 
                tag=f"chat:{self.chat}"
            )