import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ai_core.llm_providers.claude_provider import ClaudeProvider
from ai_core.llm_providers.gemini_provider import GeminiProvider
from ai_core.llm_providers.ollama_provider import OllamaProvider


def config(**overrides):
    values = {"api_key": "key", "model_name": "model", "base_url": None, "max_context_tokens": 128_000}
    values.update(overrides)
    return SimpleNamespace(**values)


# Shaped like PromptBuilder.build_messages output: rules, then the sources block.
MESSAGES = [
    {"role": "system", "content": "RULES"},
    {"role": "system", "content": "SOURCES"},
    {"role": "user", "content": "earlier question"},
    {"role": "assistant", "content": "earlier answer"},
    {"role": "user", "content": "question"},
]


class TestClaudeProvider:

    def _stream(self, messages, **kwargs):
        with patch("ai_core.llm_providers.claude_provider.anthropic.Anthropic") as client_cls:
            stream_ctx = client_cls.return_value.messages.stream
            stream_ctx.return_value.__enter__.return_value.text_stream = iter(["Hi", "!"])
            tokens = list(ClaudeProvider(config()).stream(messages, **kwargs))
        return tokens, stream_ctx.call_args.kwargs

    def test_accepts_the_arguments_llm_service_passes(self):
        tokens, _ = self._stream(MESSAGES, image_bytes=None, mime_type=None)
        assert tokens == ["Hi", "!"]

    def test_keeps_every_system_message(self):
        _, kwargs = self._stream(MESSAGES)
        assert kwargs["system"] == "RULES\n\nSOURCES"
        assert [m["role"] for m in kwargs["messages"]] == ["user", "assistant", "user"]

    def test_output_cap_follows_the_model_context(self):
        _, kwargs = self._stream(MESSAGES)
        assert kwargs["max_tokens"] > 1024

    def test_attaches_image_to_the_last_user_message(self):
        _, kwargs = self._stream(MESSAGES, image_bytes=b"img", mime_type="image/png")
        last = kwargs["messages"][-1]["content"]
        assert last[0]["type"] == "image"
        assert last[0]["source"]["media_type"] == "image/png"
        assert last[1] == {"type": "text", "text": "question"}


class TestGeminiProvider:

    def _stream(self, messages, **kwargs):
        with patch("ai_core.llm_providers.gemini_provider.genai.Client") as client_cls:
            generate = client_cls.return_value.models.generate_content_stream
            generate.return_value = iter([SimpleNamespace(text="Hel"), SimpleNamespace(text="lo")])
            tokens = list(GeminiProvider(config()).stream(messages, **kwargs))
        return tokens, generate.call_args.kwargs

    def test_streams_with_the_current_sdk(self):
        tokens, kwargs = self._stream(MESSAGES, image_bytes=None, mime_type=None)
        assert tokens == ["Hel", "lo"]
        assert kwargs["model"] == "model"

    def test_system_prompt_goes_to_system_instruction_not_a_model_turn(self):
        _, kwargs = self._stream(MESSAGES)
        assert kwargs["config"].system_instruction == "RULES\n\nSOURCES"
        assert [c.role for c in kwargs["contents"]] == ["user", "model", "user"]

    def test_attaches_image_to_the_last_user_turn(self):
        _, kwargs = self._stream(MESSAGES, image_bytes=b"img", mime_type="image/png")
        parts = kwargs["contents"][-1].parts
        assert parts[0].inline_data.mime_type == "image/png"
        assert parts[1].text == "question"


class TestOllamaProvider:

    def _stream(self, messages, **kwargs):
        lines = [
            json.dumps({"message": {"content": "Hi"}, "done": False}).encode(),
            json.dumps({"message": {"content": ""}, "done": True}).encode(),
        ]
        response = MagicMock(status_code=200)
        response.iter_lines.return_value = lines
        with patch("ai_core.llm_providers.ollama_provider.requests.post", return_value=response) as post:
            tokens = list(OllamaProvider(config()).stream(messages, **kwargs))
        return tokens, post.call_args

    def test_uses_the_chat_endpoint_with_roles(self):
        tokens, call = self._stream(MESSAGES, image_bytes=None, mime_type=None)
        assert tokens == ["Hi"]
        assert call.args[0].endswith("/api/chat")
        sent = call.kwargs["json"]["messages"]
        assert sent[0] == {"role": "system", "content": "RULES\n\nSOURCES"}
        assert [m["role"] for m in sent[1:]] == ["user", "assistant", "user"]

    def test_request_has_a_timeout(self):
        _, call = self._stream(MESSAGES)
        assert call.kwargs["timeout"]

    def test_attaches_image_to_the_last_user_message(self):
        _, call = self._stream(MESSAGES, image_bytes=b"img", mime_type="image/png")
        assert call.kwargs["json"]["messages"][-1]["images"] == ["aW1n"]


class TestOpenAIProvider:

    def test_attaching_an_image_does_not_change_the_callers_messages(self):
        from ai_core.llm_providers.openai_provider import OpenAIProvider

        messages = [{"role": "system", "content": "RULES"}, {"role": "user", "content": "question"}]
        with patch("ai_core.llm_providers.openai_provider.OpenAI") as client_cls:
            client_cls.return_value.chat.completions.create.return_value = iter([])
            list(OpenAIProvider(config()).stream(messages, image_bytes=b"img", mime_type="image/png"))
            sent = client_cls.return_value.chat.completions.create.call_args.kwargs["messages"]

        assert messages[-1]["content"] == "question"
        assert sent[-1]["content"][1]["type"] == "image_url"
