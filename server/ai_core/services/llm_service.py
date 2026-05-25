from ai_core.llm_providers.factory import ProviderFactory
from ai_core.exceptions import ProviderUnavailable
from ai_core.services.provider_service import ProviderService


class LLMService:

    def __init__(self, task_type=None, provider_id=None, ):
        if provider_id:
            provider_config = ProviderService.get_chat_provider(provider_id)
        else:
            provider_config = ProviderService.get_default_chat_provider()

        if not provider_config:
            raise ProviderUnavailable("LLM provider not available")

        self.provider_config = provider_config
        self.provider = ProviderFactory.get_provider(task_type=task_type, provider_id=provider_id)


    def stream(self, messages: list[dict], image_bytes=None, mime_type=None):
        for token in self.provider.stream(messages, image_bytes, mime_type):
            yield token
