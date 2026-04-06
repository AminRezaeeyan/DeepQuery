import pkgutil
import importlib

from ai_core.providers.base import PROVIDER_REGISTRY
from ai_core.models import LLMProvider
from ai_core.exceptions import ProviderUnavailable


class ProviderFactory:
    _initialized = False

    @classmethod
    def _auto_import_providers(cls):
        if cls._initialized:
            return

        import ai_core.providers as providers_pkg

        for _, module_name, _ in pkgutil.iter_modules(providers_pkg.__path__):
            importlib.import_module(f"ai_core.providers.{module_name}")

        cls._initialized = True

    @classmethod
    def get_provider(cls, provider_id=None):
        cls._auto_import_providers()

        if provider_id:
            provider = (
                LLMProvider.objects
                .filter(id=provider_id, is_active=True)
                .first()
            )

            if not provider:
                raise ProviderUnavailable("Requested provider not found or inactive")

        else:
            provider = (
                LLMProvider.objects
                .filter(is_default=True, is_active=True)
                .first()
            )

            if not provider:
                raise ProviderUnavailable("No default active LLM provider configured")

        provider_class = PROVIDER_REGISTRY.get(provider.provider_type)

        if not provider_class:
            raise ProviderUnavailable(f"Unknown provider type: {provider.provider_type}")

        return provider_class(provider)
