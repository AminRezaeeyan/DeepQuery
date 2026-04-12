from typing import List, Optional
from embedding_providers.factory import EmbeddingProviderFactory
from ai_core.exceptions import ProviderUnavailable


class EmbeddingService:
    """
    High-level embedding service that abstracts away provider differences.
    """

    def __init__(self, provider_id: Optional[int] = None):
        """
        If provider_id is provided, use that provider.
        Otherwise, use the active embedding provider.
        """
        try:
            self.provider = EmbeddingProviderFactory.get_provider(provider_id)
        except ProviderUnavailable as exc:
            raise ProviderUnavailable(f"EmbeddingService initialization failed: {exc}")


    @staticmethod
    def _chunk(texts: List[str], chunk_size: int = 32):
        """
        Splits long text lists into batches for providers that require batching.
        """
        for i in range(0, len(texts), chunk_size):
            yield texts[i:i + chunk_size]


    def embed_query(self, text: str):
        """
        Generate a single embedding for a search/query text.
        """
        return self.provider.embed_query(text)

    def embed_documents(self, texts: List[str], batch_size: int = 32):
        """
        Generate embeddings for multiple texts.

        Returns:
            A list of vectors (one per text).
        """
        results = []

        for batch in self._chunk(texts, batch_size):
            batch_embeddings = self.provider.embed_documents(batch)
            results.extend(batch_embeddings)

        return results

    def provider_type(self):
        return self.provider.provider_config.provider_type

    def provider_name(self):
        return self.provider.provider_config.name

    def is_available(self):
        return self.provider.is_available()
