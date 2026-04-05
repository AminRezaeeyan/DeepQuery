import google.generativeai as genai
from .base import LLMProviderBase


class GeminiProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        genai.configure(api_key=provider_config.api_key)

        self.model = genai.GenerativeModel(
            provider_config.model_name
        )

    def stream(self, prompt):

        response = self.model.generate_content(
            prompt,
            stream=True
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text
