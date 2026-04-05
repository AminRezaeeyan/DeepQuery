from ai_core.models import LLMProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .claude_provider import ClaudeProvider
from .ollama_provider import OllamaProvider


class ProviderFactory:

    PROVIDER_MAP = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "ollama": OllamaProvider,
    }

    @classmethod
    def get_active_provider(cls):

        provider = LLMProvider.objects.filter(
            is_active=True
        ).first()

        if not provider:
            raise Exception("No active LLM provider configured")

        provider_class = cls.PROVIDER_MAP.get(provider.provider_type)

        if not provider_class:
            raise Exception("Unsupported provider")

        return provider_class(provider)
