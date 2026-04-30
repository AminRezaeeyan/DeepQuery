from openai import OpenAI
from .base import EmbeddingProviderBase, register_embedding_provider


@register_embedding_provider("openai")
class OpenAIEmbeddingProvider(EmbeddingProviderBase):
    def __init__(self, provider_model):
        super().__init__(provider_model)
        self.client = OpenAI(api_key=self.provider_model.api_key, base_url=provider_model.base_url)

    def embed_documents(self, texts):
        resp = self.client.embeddings.create(
            model=self.provider_model.model_name, 
            input=texts
        )
        return [d.embedding for d in resp.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]

    def is_available(self):
        return bool(self.provider_model.api_key)
    
    def count_tokens(self, text):
        from ai_core.services.token_service import TokenService
        return TokenService.count_tokens(text)
