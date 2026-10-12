from google import genai
from google.genai import types
from .base import EmbeddingProviderBase, register_embedding_provider


@register_embedding_provider("gemini")
class GeminiEmbeddingProvider(EmbeddingProviderBase):
    def __init__(self, provider_model):
        super().__init__(provider_model)
        self.client = genai.Client(api_key=provider_model.api_key)

    def _embed(self, texts, task_type):
        resp = self.client.models.embed_content(
            model=self.provider_model.model_name,
            contents=texts,
            # Match the vector column size configured for this provider.
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimension),
        )
        return [e.values for e in resp.embeddings]

    def embed_documents(self, texts):
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text):
        return self._embed([text], "RETRIEVAL_QUERY")[0]

    def is_available(self):
        return bool(self.provider_model.api_key)


    def count_tokens(self, text):
        from ai_core.services.token_service import TokenService
        return TokenService.count_tokens(text)
