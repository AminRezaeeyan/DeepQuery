import pkgutil
import importlib

from ai_core.llm_providers.base import PROVIDER_REGISTRY
from ai_core.exceptions import ProviderUnavailable
from ai_core.services.task_provider_resolver import TaskProviderResolver


class ProviderFactory:
    _initialized = False

    @classmethod
    def _auto_import_providers(cls):
        if cls._initialized:
            return

        import ai_core.llm_providers as providers_pkg

        for _, module_name, _ in pkgutil.iter_modules(providers_pkg.__path__):
            importlib.import_module(f"ai_core.llm_providers.{module_name}")

        cls._initialized = True

    @classmethod
    def get_provider(cls, task_type=None, provider_id=None):
        cls._auto_import_providers()

        provider = TaskProviderResolver.get_provider_for_task(
            task_type=task_type,
            provider_id=provider_id,
        )

        provider_class = PROVIDER_REGISTRY.get(provider.provider_type)

        if not provider_class:
            raise ProviderUnavailable(f"Unknown provider type: {provider.provider_type}")

        return provider_class(provider)
