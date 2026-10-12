from google import genai
from google.genai import types

from ai_core.llm_providers.base import LLMProviderBase, register_provider, split_system_messages
from ai_core.exceptions import ContextLimitExceededError
from ai_core.services.token_service import TokenService


@register_provider("gemini")
class GeminiProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.client = genai.Client(api_key=provider_config.api_key)
        self.model = provider_config.model_name

    def _convert_messages(self, messages, image_bytes=None, mime_type=None):

        contents = []

        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))

        if image_bytes and mime_type:
            for content in reversed(contents):
                if content.role == "user":
                    content.parts.insert(0, types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
                    break

        return contents

    def stream(self, messages, image_bytes=None, mime_type=None):

        system_prompt, chat_messages = split_system_messages(messages)
        contents = self._convert_messages(chat_messages, image_bytes, mime_type)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt or None,
            max_output_tokens=TokenService.get_output_reserve(self.provider_config.max_context_tokens),
        )

        try:
            response = self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            msg = str(e).lower()

            if "context" in msg or "token" in msg or "limit" in msg:
                raise ContextLimitExceededError(str(e))

            raise
