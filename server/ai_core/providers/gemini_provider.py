import google.genai as genai

from ai_core.providers.base import LLMProviderBase, register_provider
from ai_core.exceptions import ContextLimitExceededError


@register_provider("gemini")
class GeminiProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        genai.configure(api_key=provider_config.api_key)

        self.model = genai.GenerativeModel(
            provider_config.model_name
        )

    def _convert_messages(self, messages):

        gemini_messages = []

        for m in messages:
            role = "user" if m["role"] == "user" else "model"

            gemini_messages.append({
                "role": role,
                "parts": [m["content"]]
            })

        return gemini_messages

    def stream(self, messages):

        converted = self._convert_messages(messages)

        try:
            response = self.model.generate_content(
                converted,
                stream=True
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            msg = str(e).lower()

            if "context" in msg or "token" in msg or "limit" in msg:
                raise ContextLimitExceededError(str(e))

            raise
