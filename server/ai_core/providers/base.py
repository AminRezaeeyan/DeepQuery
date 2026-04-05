PROVIDER_REGISTRY = {}


def register_provider(provider_name):
    """
    Decorator that auto-registers provider classes.
    """
    def decorator(cls):
        PROVIDER_REGISTRY[provider_name] = cls
        return cls
    return decorator


class LLMProviderBase:

    def __init__(self, provider_config):
        self.provider_config = provider_config

    def stream(self, prompt: str):
        raise NotImplementedError
