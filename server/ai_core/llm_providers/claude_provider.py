import base64

import anthropic

from ai_core.llm_providers.base import LLM_TIMEOUT, LLMProviderBase, register_provider, split_system_messages
from ai_core.exceptions import ContextLimitExceededError
from ai_core.services.token_service import TokenService


@register_provider("claude")
class ClaudeProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.client = anthropic.Anthropic(
            api_key=provider_config.api_key,
            timeout=LLM_TIMEOUT,
        )

        self.model = provider_config.model_name

    def stream(self, messages, image_bytes=None, mime_type=None):

        system_prompt, chat_messages = split_system_messages(messages)
        chat_messages = [dict(m) for m in chat_messages]

        if image_bytes and mime_type:
            for message in reversed(chat_messages):
                if message["role"] == "user":
                    message["content"] = [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("utf-8"),
                            },
                        },
                        {"type": "text", "text": message["content"]},
                    ]
                    break

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=TokenService.get_output_reserve(self.provider_config.max_context_tokens),
                system=system_prompt or anthropic.NOT_GIVEN,
                messages=chat_messages
            ) as stream:

                for text in stream.text_stream:
                    yield text

        except anthropic.BadRequestError as e:
            msg = str(e).lower()

            if "context" in msg or "token" in msg or "limit" in msg:
                raise ContextLimitExceededError(str(e))

            raise
