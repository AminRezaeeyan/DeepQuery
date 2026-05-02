from typing import List, Tuple, Optional

from ai_core.services.embedding_service import EmbeddingService
from ai_core.services.token_service import TokenService
from documents.models import Document


class DocumentRAGService:
    """
    Retrieve and build a context block from user-uploaded documents
    scoped to a chat.
    Uses EmbeddingService to perform pgvector search filtered by chat tag.
    """

    def __init__(self, chat_id: int , provider_id: Optional[int] = None):
        self.chat_id = chat_id
        self.embedding_service = EmbeddingService(provider_id=provider_id)

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar document chunks belonging to this chat.
        Returns tuples: (Document instance, score).
        """
        tag = f"chat:{self.chat_id}"

        results = self.embedding_service.search(
            query=query,
            content_model=Document,
            limit=limit,
            tag=tag,
        )

        return results


    def build_knowledge_context(
        self,
        query: str,
        token_limit: int,
        max_candidates: int = 10,
    ) -> str:
        """
        Gathers top document chunks for RAG context,
        truncated to fit within token_limit.
        """
        if token_limit <= 0:
            return ""

        results = self.search(query, limit=max_candidates)
        if not results:
            return ""

        results.sort(key=lambda x: x[1], reverse=True)

        total_tokens = 0
        selected_chunks: list[str] = []

        for doc, score in results:
            text = getattr(doc, "extracted_text", None)
            if not text:
                continue
            tok_count = TokenService.count_tokens(text)
            if total_tokens + tok_count > token_limit:
                continue

            selected_chunks.append(text.strip())
            total_tokens += tok_count

        if not selected_chunks:
            return ""

        block = "\n\n--- DOCUMENT KNOWLEDGE ---\n\n"
        block += "\n\n---\n\n".join(selected_chunks)

        return block
