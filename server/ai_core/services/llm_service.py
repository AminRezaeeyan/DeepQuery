from ai_core.models import LLMProvider
from ai_core.providers.factory import ProviderFactory
from ai_core.exceptions import ProviderUnavailable
from ai_core.services.provider_service import ProviderService

class LLMService:

    def __init__(self, provider_id=None):

        if provider_id:
            provider_config = ProviderService.get_provider(provider_id)
        else:
            provider_config = ProviderService.get_default_provider()

        if not provider_config:
            raise ProviderUnavailable("LLM provider not found or inactive")

        self.provider_config = provider_config   # DB model
        self.provider = ProviderFactory.get_provider(provider_id)

    def stream(self, messages: list[dict]):
        for token in self.provider.stream(messages):
            yield token
