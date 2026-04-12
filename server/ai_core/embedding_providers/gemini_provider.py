import google.genai as genai
from .base import EmbeddingProviderBase, register_embedding_provider


@register_embedding_provider("gemini")
class GeminiEmbeddingProvider(EmbeddingProviderBase):
    def __init__(self, provider_config):
        super().__init__(provider_config)
        genai.configure(api_key=self.provider_config.api_key)

    def embed_documents(self, texts):
        # Gemini handles batching internally
        resp = genai.embed_content(
            model=f"models/{self.provider_config.model_name}",
            content=texts,
            task_type="retrieval_document"
        )
        return resp["embedding"]

    def embed_query(self, text):
        resp = genai.embed_content(
            model=f"models/{self.provider_config.model_name}",
            content=text,
            task_type="retrieval_query"
        )
        return resp["embedding"]

    def is_available(self):
        return bool(self.provider_config.api_key)
