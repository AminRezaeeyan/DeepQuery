import json
from dataclasses import dataclass, field

PROVIDER_REGISTRY = {}

# Seconds. Streaming reads wait at most this long between chunks.
LLM_TIMEOUT = 120


def register_provider(provider_name):
    """
    Decorator that auto-registers provider classes.
    """
    def decorator(cls):
        PROVIDER_REGISTRY[provider_name] = cls
        return cls
    return decorator


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)
    # Set when the model sent arguments that aren't valid JSON; the agent reports it back.
    error: str | None = None

    @classmethod
    def from_raw(cls, id: str, name: str, raw_arguments: str) -> "ToolCall":
        try:
            arguments = json.loads(raw_arguments or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be a JSON object")
            return cls(id=id, name=name, arguments=arguments)
        except ValueError as e:
            return cls(id=id, name=name, error=f"Invalid arguments: {e}")


class LLMProviderBase:
    # Providers that implement stream_turn() can run the research agent's tool loop;
    # the others answer through the single-pass pipeline.
    supports_tools = False

    def __init__(self, provider_config):
        self.provider_config = provider_config

    def stream(self, messages, image_bytes=None, mime_type=None):
        raise NotImplementedError

    def stream_turn(self, messages, tools, tool_choice="auto"):
        """
        One model turn with tools available. Yields ("text", delta) while the model
        writes an answer and, if it calls tools instead, ends with
        ("tool_calls", [ToolCall, ...]).

        `messages` use the OpenAI chat shape: assistant turns may carry
        "tool_calls", and tool results are {"role": "tool", "tool_call_id", "content"}.
        `tools` are {"name", "description", "parameters": JSON schema}.
        `tool_choice` is "auto" or "none" (answer now, no more tools).
        """
        raise NotImplementedError


def split_system_messages(messages):
    """
    Returns (system_text, other_messages). The prompt builder sends several
    system messages (rules, memory, sources); providers with a single system
    field need all of them, in order.
    """
    system_parts = [m["content"] for m in messages if m["role"] == "system" and m["content"]]
    others = [m for m in messages if m["role"] != "system"]
    return "\n\n".join(system_parts), others
