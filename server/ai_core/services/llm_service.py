from ..providers.factory import ProviderFactory


class LLMService:
    def __init__(self):
        self.provider = ProviderFactory.get_active_provider()

    def stream(self, prompt: str):
        for token in self.provider.stream(prompt):
            yield token