import anthropic
from .base import LLMProviderBase, register_provider


@register_provider('claude')
class ClaudeProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.client = anthropic.Anthropic(
            api_key=provider_config.api_key
        )

        self.model = provider_config.model_name

    def stream(self, prompt):

        with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ],
        ) as stream:

            for text in stream.text_stream:
                yield text
