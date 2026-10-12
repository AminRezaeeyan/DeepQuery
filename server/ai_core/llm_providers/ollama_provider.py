import base64
import requests
import json

from ai_core.llm_providers.base import LLMProviderBase, register_provider, split_system_messages
from ai_core.exceptions import ContextLimitExceededError


@register_provider("ollama")
class OllamaProvider(LLMProviderBase):

    # Generous: local models can take a while to load before the first token.
    TIMEOUT = (10, 300)

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.base_url = provider_config.base_url or "http://localhost:11434"
        self.model = provider_config.model_name

    def _build_messages(self, messages, image_bytes=None, mime_type=None):

        system_prompt, chat_messages = split_system_messages(messages)

        result = [{"role": "system", "content": system_prompt}] if system_prompt else []
        result += [{"role": m["role"], "content": m["content"]} for m in chat_messages]

        if image_bytes and mime_type:
            for message in reversed(result):
                if message["role"] == "user":
                    message["images"] = [base64.b64encode(image_bytes).decode("utf-8")]
                    break

        return result

    def stream(self, messages, image_bytes=None, mime_type=None):

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": self._build_messages(messages, image_bytes, mime_type),
                    "stream": True
                },
                stream=True,
                timeout=self.TIMEOUT,
            )

            if response.status_code == 400:
                raise ContextLimitExceededError(response.text)

            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                data = json.loads(line.decode("utf-8"))

                content = data.get("message", {}).get("content")
                if content:
                    yield content

                if data.get("done"):
                    break

        except requests.exceptions.RequestException as e:
            raise Exception(f"Could not connect to Ollama: {e}")
