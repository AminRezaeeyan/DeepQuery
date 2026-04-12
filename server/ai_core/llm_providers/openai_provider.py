from ai_core.llm_providers.base import LLMProviderBase, register_provider
from openai import OpenAI


@register_provider("openai")
class OpenAIProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.client = OpenAI(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url
        )

        self.model = provider_config.model_name

    def stream(self, messages):

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except BadRequestError as e:
            msg = str(e).lower()

            if "context" in msg or "maximum context length" in msg:
                raise ContextLimitExceededError(str(e))

            raise
