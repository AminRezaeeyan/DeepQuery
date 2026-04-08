from ..providers.factory import ProviderFactory


class LLMService:
    def __init__(self, provider_id=None):
        self.provider = ProviderFactory.get_provider(provider_id)

    def stream(self, messages: list[dict]):
         """
        messages: [
          {"role": "system" | "user" | "assistant", "content": str},
          ...
        ]
        """
        for token in self.provider.stream(messages):
            yield token
