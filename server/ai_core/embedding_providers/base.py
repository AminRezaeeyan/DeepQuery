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

    def __init__(self, provider_model):
        """
        provider_model = instance of EmbeddingProvider Django model
        """
        self.provider_model = provider_model

        self.model_name = provider_model.model_name
        self.provider_type = provider_model.provider_type
        self.api_key = provider_model.api_key
        self.max_tokens = provider_model.max_tokens
        self.dimension = provider_model.dimension


    def embed_documents(self, texts):
        raise NotImplementedError

    def embed_query(self, text):
        raise NotImplementedError

    def is_available(self):
        raise NotImplementedError


    def count_tokens(self, text: str) -> int:
        """
        Must be implemented by each provider.
        """
        raise NotImplementedError

    def max_input_tokens(self):
        """
        Unified accessor so chunking code is clean.
        """
        return self.max_tokens

