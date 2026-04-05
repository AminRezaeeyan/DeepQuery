import requests
from .base import LLMProviderBase


class OllamaProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.base_url = provider_config.base_url or "http://localhost:11434"
        self.model = provider_config.model_name

    def stream(self, prompt):

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": True
            },
            stream=True
        )

        for line in response.iter_lines():
            if line:
                yield line.decode()
