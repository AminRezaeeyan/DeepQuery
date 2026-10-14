import json

import pytest
from unittest.mock import patch

from ai_core.exceptions import ContextLimitExceededError
from chats.models import Message


@pytest.fixture
def generation():
    with patch("chats.services.chat_service.ChatGenerationService") as service_cls, \
         patch("chats.tasks.generate_chat_title.delay"):
        yield service_cls.return_value


def post_message(client, chat, content="question"):
    return client.post(f"/api/chats/{chat.uuid}/messages/", {"content": content})


def failing_stream(*args, **kwargs):
    yield {"type": "text", "text": "Partial "}
    raise RuntimeError("provider exploded")


@pytest.mark.django_db
class TestStreamErrors:

    def test_prompt_too_large_is_a_400_before_streaming(self, auth_client, chat, generation):
        generation.prepare.side_effect = ContextLimitExceededError("Prompt is too large for the model context window.")

        response = post_message(auth_client, chat)

        assert response.status_code == 400
        assert "too large" in json.dumps(response.json())

    def test_failure_mid_stream_ends_with_a_detectable_error(self, auth_client, chat, generation):
        generation.answer_events.side_effect = failing_stream

        response = post_message(auth_client, chat)
        events = [json.loads(line) for line in b"".join(response.streaming_content).decode().splitlines()]

        assert response["Content-Type"] == "application/x-ndjson"
        assert events[0] == {"type": "text", "text": "Partial "}
        assert events[-1]["type"] == "error" and events[-1]["detail"]
        assert "provider exploded" not in events[-1]["detail"]
        assert not Message.objects.filter(chat=chat, role=Message.Role.ASSISTANT).exists()

    def test_successful_stream_has_no_error_marker(self, auth_client, chat, generation):
        generation.answer_events.return_value = iter([{"type": "text", "text": "All "}, {"type": "text", "text": "good"}])

        lines = b"".join(post_message(auth_client, chat).streaming_content).decode().splitlines()

        assert [json.loads(line) for line in lines] == [{"type": "text", "text": "All "}, {"type": "text", "text": "good"}]
        assert Message.objects.get(chat=chat, role=Message.Role.ASSISTANT).content == "All good"
