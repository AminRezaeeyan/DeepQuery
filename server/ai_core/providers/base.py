class LLMProviderBase():
    def __init__(self, provider_config):
        self.provider_config = provider_config

    def stream(self, prompt: str):
        raise NotImplementedError