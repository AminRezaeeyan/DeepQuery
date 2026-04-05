from openai import OpenAI
from .base import LLMProviderBase


class OpenAIProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.client = OpenAI(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url
        )

        self.model = provider_config.model_name

    def stream(self, prompt):

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            stream=True
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
