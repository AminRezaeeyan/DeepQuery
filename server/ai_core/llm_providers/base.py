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

    def stream(self, messages, image_bytes=None, mime_type=None):
        raise NotImplementedError


def split_system_messages(messages):
    """
    Returns (system_text, other_messages). The prompt builder sends several
    system messages (rules, memory, sources); providers with a single system
    field need all of them, in order.
    """
    system_parts = [m["content"] for m in messages if m["role"] == "system" and m["content"]]
    others = [m for m in messages if m["role"] != "system"]
    return "\n\n".join(system_parts), others
