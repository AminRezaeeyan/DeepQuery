from typing import List, Dict, Optional
from ai_core.services.embedding_service import EmbeddingService
from ai_core.tasks import extract_and_embed_facts_task
from ai_core.models import MemoryFact
from ai_core.services.token_service import TokenService


class LongTermMemoryService:
    """
    Handles:
    - Fact extraction trigger (async)
    - Vector search over stored memories
    - Formatting memory context for prompts
    """

    def __init__(self, user_id, provider_id: Optional[int] = None, enabled=True):
        self.user_id = user_id
        self.provider_id = provider_id
        self.embedder = EmbeddingService(provider_id=provider_id)
        self.enabled=True

    def store_from_message(self, chat_id, text):
        """
        Triggers async fact extraction + embedding.
        """
        if not self.enabled:
            return
        
        extract_and_embed_facts_task.delay(
            user_id=self.user_id,
            chat_id=chat_id,
            text=text,
            provider_id=self.provider_id,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.75,
    ) -> List[MemoryFact]:
        
        if not self.enabled:
            return []

        results = self.embedder.search(
            query=query,
            content_model=MemoryFact,
            limit=limit,
            tag=f"user:{self.user_id}"
        )

        filtered = [
            instance
            for instance, score in results
            if score >= min_score and instance.user_id == self.user_id
        ]

        return filtered



    def build_memory_context(
        self,
        query: str,
        token_limit: int,
        max_candidates: int = 10,
    ) -> str:
        """
        Retrieve relevant memories and trim them to fit inside a token_limit.
        """
        if not self.enabled:
            return ''

        candidates = self.search(query=query, limit=max_candidates, min_score=0.1)

        if not candidates or token_limit <= 0:
            return ""

        selected = []
        current_tokens = 0

        for mem in candidates:
            text = f"- {mem.fact}"
            tokens = TokenService.count_tokens(text)

            # If adding this fact exceeds the budget → stop
            if current_tokens + tokens > token_limit:
                break

            selected.append(text)
            current_tokens += tokens

        if not selected:
            return ""

        return "\n".join(selected)

