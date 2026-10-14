import base64
from ai_core.llm_providers.base import LLM_TIMEOUT, LLMProviderBase, ToolCall, register_provider
from openai import BadRequestError, OpenAI
from ai_core.exceptions import ContextLimitExceededError

@register_provider("openai")
class OpenAIProvider(LLMProviderBase):
    supports_tools = True

    def __init__(self, provider_config):
        super().__init__(provider_config)
        self.client = OpenAI(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url,
            timeout=LLM_TIMEOUT,
        )
        self.model = provider_config.model_name

    def stream(self, messages, image_bytes=None, mime_type=None):
        messages = with_image(messages, image_bytes, mime_type)

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

    def stream_turn(self, messages, tools, tool_choice="auto"):
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[{"type": "function", "function": tool} for tool in tools],
                tool_choice=tool_choice if tool_choice in ("auto", "none", "required") else {"type": "function", "function": {"name": tool_choice}},
                stream=True,
            )

            # Tool calls arrive in fragments, keyed by their index in the turn.
            calls = {}
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield "text", delta.content
                for part in delta.tool_calls or []:
                    call = calls.setdefault(part.index, {"id": "", "name": "", "arguments": ""})
                    call["id"] = part.id or call["id"]
                    if part.function:
                        call["name"] += part.function.name or ""
                        call["arguments"] += part.function.arguments or ""

            if calls:
                yield "tool_calls", [ToolCall.from_raw(c["id"], c["name"], c["arguments"]) for _, c in sorted(calls.items())]

        except BadRequestError as e:
            msg = str(e).lower()
            if "context" in msg or "maximum context length" in msg:
                raise ContextLimitExceededError(str(e))
            raise


def with_image(messages, image_bytes=None, mime_type=None):
    """A copy of the messages with the image attached to the last user turn."""
    # Work on a copy: callers keep using their messages (e.g. to log the prompt).
    messages = [dict(m) for m in messages]
    if not (image_bytes and mime_type):
        return messages
    image_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
    image_part = {"type": "image_url", "image_url": {"url": image_url}}
    for message in reversed(messages):
        if message["role"] == "user":
            content = message["content"]
            message["content"] = ([{"type": "text", "text": content}] if isinstance(content, str) else list(content)) + [image_part]
            break
    return messages
