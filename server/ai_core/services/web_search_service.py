import requests
from bs4 import BeautifulSoup
import re

from django.conf import settings

from ai_core.services.llm_service import LLMService
from ai_core.services.token_service import TokenService
from documents.models import Document
from .embedding_service import EmbeddingService

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
    


class WebPageFetcher:

    def fetch(self, url: str) -> str:
        try:
            res = requests.get(url, timeout=5)
            res.raise_for_status()

            soup = BeautifulSoup(res.text, "html.parser")

            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            text = soup.get_text(separator="\n")
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n+', '\n', text)


            return text[:20000]

        except Exception:
            return ""

class SerperProvider:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://google.serper.dev/search"

    def search(self, query: str):
        # payload = {"q": f"{query}"} 
        # headers = {
        #     "X-API-KEY": self.api_key,
        #     "Content-Type": "application/json"
        # }
        # response = requests.post(self.url, json=payload, headers=headers)
        # response.raise_for_status()

        # data = response.json()
        # results = []

        # for item in data.get("organic", [])[:5]:
        #     results.append({
        #         "title": item.get("title"),
        #         "url": item.get("link"),
        #         "snippet": item.get("snippet"),
        #     })
        # return results
        return []    

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
            print(f"Search error: {e}")
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

        urls_to_process = extract_urls(prompt)

        # If no explicit URLs, generate query and search
        if not urls_to_process:
            query = self.query_generator.generate(prompt)
            results = self.search_service.search(query)
            urls_to_process = [r["url"] for r in results[:self.MAX_SEARCH_RESULTS]]

        for url in urls_to_process:
            page_text = self.fetcher.fetch(url)

            print(f"Fetched {len(page_text)} chars from {url}")
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