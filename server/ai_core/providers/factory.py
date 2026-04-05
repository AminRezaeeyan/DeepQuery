import pkgutil
import importlib
from ai_core.providers.base import PROVIDER_REGISTRY
from ai_core.models import LLMProvider


class ProviderFactory:

    @staticmethod
    def _auto_import_providers():
        import ai_core.providers as providers_pkg

        package_path = providers_pkg.__path__

        for _, module_name, _ in pkgutil.iter_modules(package_path):
            importlib.import_module(f"ai_core.providers.{module_name}")

    @classmethod
    def get_active_provider(cls):
        cls._auto_import_providers()

        provider = (
            LLMProvider.objects.filter(is_active=True)
            .first()
        )

        if not provider:
            raise Exception("No active LLM provider configured")

        provider_class = PROVIDER_REGISTRY.get(provider.provider_type)

        if not provider_class:
            raise Exception(f"Unknown provider type: {provider.provider_type}")

        return provider_class(provider)
