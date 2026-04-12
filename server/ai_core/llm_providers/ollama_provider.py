import requests
import json

from ai_core.llm_providers.base import LLMProviderBase, register_provider
from ai_core.exceptions import ContextLimitExceededError


@register_provider("ollama")
class OllamaProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)

        self.base_url = provider_config.base_url or "http://localhost:11434"
        self.model = provider_config.model_name

    def _messages_to_prompt(self, messages):

        parts = []

        for m in messages:
            role = m["role"]
            content = m["content"]

            if role == "system":
                parts.append(f"System:\n{content}")
            elif role == "user":
                parts.append(f"User:\n{content}")
            elif role == "assistant":
                parts.append(f"Assistant:\n{content}")

        parts.append("Assistant:")

        return "\n\n".join(parts)

    def stream(self, messages):

        prompt = self._messages_to_prompt(messages)

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": True
                },
                stream=True
            )

            if response.status_code == 400:
                raise ContextLimitExceededError(response.text)

            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                data = json.loads(line.decode("utf-8"))

                if "response" in data and data["response"]:
                    yield data["response"]

                if data.get("done"):
                    break

        except requests.exceptions.RequestException as e:
            raise Exception(f"Could not connect to Ollama: {e}")
