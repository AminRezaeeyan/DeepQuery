EMBEDDING_PROVIDER_REGISTRY = {}


def register_embedding_provider(provider_type: str):
    """
    Decorator to register embedding provider classes.
    """
    def decorator(cls):
        EMBEDDING_PROVIDER_REGISTRY[provider_type] = cls
        return cls
    return decorator


class EmbeddingProviderBase:
    """
    Base class that all embedding providers must inherit from.
    """
    provider_type: str = None

    def __init__(self, model_name: str, api_key: str = None, **kwargs):
        self.model_name = model_name
        self.api_key = api_key

    def embed_documents(self, texts):
        raise NotImplementedError

    def embed_query(self, text):
        raise NotImplementedError

    def is_available(self):
        raise NotImplementedError
