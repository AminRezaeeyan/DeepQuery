from ai_core.models import LLMProvider
from ai_core.exceptions import ProviderUnavailable

class ProviderService:

    @staticmethod
    def get_default_provider_id():
        provider = (
            LLMProvider.objects
            .filter(is_default=True, is_active=True)
            .only("id")
            .first()
        )

        if not provider:
            raise ProviderUnavailable("No default active LLM provider configured")

        return provider.id
    
    @staticmethod
    def validate_provider_id(provider_id):
        provider = LLMProvider.objects.filter(id=provider_id, is_active=True).first()
        if not provider:
            raise ProviderUnavailable("Provider not found or inactive.")