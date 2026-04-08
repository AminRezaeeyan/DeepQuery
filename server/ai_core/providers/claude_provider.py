import anthropic

from ai_core.providers.base import LLMProviderBase, register_provider
from ai_core.exceptions import ContextLimitExceededError


@register_provider("claude")
class ClaudeProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.client = anthropic.Anthropic(
            api_key=provider_config.api_key
        )

        self.model = provider_config.model_name

    def stream(self, messages):

        system_prompt = None
        chat_messages = []

        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                chat_messages.append(m)

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=chat_messages
            ) as stream:

                for text in stream.text_stream:
                    yield text

        except anthropic.BadRequestError as e:
            msg = str(e).lower()

            if "context" in msg or "token" in msg or "limit" in msg:
                raise ContextLimitExceededError(str(e))

            raise
