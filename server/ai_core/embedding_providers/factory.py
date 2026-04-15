import pkgutil
import importlib

from .base import EMBEDDING_PROVIDER_REGISTRY
from ai_core.exceptions import ProviderUnavailable
from ai_core.models import EmbeddingProvider


class EmbeddingProviderFactory:
    _initialized = False

    @classmethod
    def _auto_import_providers(cls):
        """
        Automatically import all provider modules so they auto-register.
        """
        if cls._initialized:
            return

        import ai_core.embedding_providers as providers_pkg

        for _, module_name, _ in pkgutil.iter_modules(providers_pkg.__path__):
            importlib.import_module(f"ai_core.embedding_providers.{module_name}")

        cls._initialized = True

    @classmethod
    def get_provider(cls, provider_id=None):
        """
        Returns a provider instance. 
        If provider_id is provided -> specific provider.
        If provider_id is None -> the active provider.
        """
        cls._auto_import_providers()

        if provider_id:
            provider = EmbeddingProvider.objects.filter(id=provider_id).first()
        else:
            provider = EmbeddingProvider.objects.filter(is_active=True).first()

        if not provider:
            raise ProviderUnavailable("No embedding provider found.")

        return cls.from_model(provider)

    @classmethod
    def from_model(cls, provider_instance):
        """
        Creates a provider instance directly from an EmbeddingProvider model object.
        """
        cls._auto_import_providers()

        provider_class = EMBEDDING_PROVIDER_REGISTRY.get(provider_instance.provider_type)

        if not provider_class:
            raise ProviderUnavailable(
                f"Unknown embedding provider type: {provider_instance.provider_type}"
            )

        return provider_class(provider_instance)

    @classmethod
    def active(cls):
        """
        Shortcut to get the currently active provider instance.
        """
        return cls.get_provider(provider_id=None)
