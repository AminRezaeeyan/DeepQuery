import base64
from ai_core.llm_providers.base import LLM_TIMEOUT, LLMProviderBase, register_provider
from openai import BadRequestError, OpenAI
from ai_core.exceptions import ContextLimitExceededError

@register_provider("openai")
class OpenAIProvider(LLMProviderBase):

    def __init__(self, provider_config):
        super().__init__(provider_config)
        self.client = OpenAI(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url,
            timeout=LLM_TIMEOUT,
        )
        self.model = provider_config.model_name

    def stream(self, messages, image_bytes=None, mime_type=None):
        # Work on a copy: callers keep using their messages (e.g. to log the prompt).
        messages = [dict(m) for m in messages]
        if image_bytes and mime_type:
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:{mime_type};base64,{base64_image}"
            
            for message in reversed(messages):
                if message["role"] == "user":
                    if isinstance(message["content"], str):
                        message["content"] = [
                            {"type": "text", "text": message["content"]},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    elif isinstance(message["content"], list):
                        message["content"] = message["content"] + [
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    break

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
