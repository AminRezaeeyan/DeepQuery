from openai import OpenAI
from .base import EmbeddingProviderBase, register_embedding_provider


@register_embedding_provider("openai")
class OpenAIEmbeddingProvider(EmbeddingProviderBase):
    def __init__(self, provider_config):
        super().__init__(provider_config)
        self.client = OpenAI(api_key=self.provider_config.api_key)

    def embed_documents(self, texts):
        resp = self.client.embeddings.create(
            model=self.provider_config.model_name, 
            input=texts
        )
        return [d.embedding for d in resp.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]

    def is_available(self):
        return bool(self.provider_config.api_key)
