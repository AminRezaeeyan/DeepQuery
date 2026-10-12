import json

import pytest
from unittest.mock import patch

from ai_core.exceptions import ContextLimitExceededError
from chats.models import Message
from chats.services.chat_service import STREAM_ERROR_MARKER


@pytest.fixture
def generation():
    with patch("chats.services.chat_service.ChatGenerationService") as service_cls, \
         patch("chats.tasks.generate_chat_title.delay"):
        yield service_cls.return_value


def post_message(client, chat, content="question"):
    return client.post(f"/api/chats/{chat.uuid}/messages/", {"content": content})


def failing_stream(*args, **kwargs):
    yield "Partial "
    raise RuntimeError("provider exploded")


@pytest.mark.django_db
class TestStreamErrors:

    def test_prompt_too_large_is_a_400_before_streaming(self, auth_client, chat, generation):
        generation.prepare.side_effect = ContextLimitExceededError("Prompt is too large for the model context window.")

        response = post_message(auth_client, chat)

        assert response.status_code == 400
        assert "too large" in json.dumps(response.json())

    def test_failure_mid_stream_ends_with_a_detectable_error(self, auth_client, chat, generation):
        generation.stream_prepared.side_effect = failing_stream

        response = post_message(auth_client, chat)
        body = b"".join(response.streaming_content).decode()

        text, _, error = body.partition(STREAM_ERROR_MARKER)
        assert text == "Partial "
        assert json.loads(error)["detail"]
        assert "provider exploded" not in error
        assert not Message.objects.filter(chat=chat, role=Message.Role.ASSISTANT).exists()

    def test_successful_stream_has_no_error_marker(self, auth_client, chat, generation):
        generation.stream_prepared.return_value = iter(["All ", "good"])

        body = b"".join(post_message(auth_client, chat).streaming_content).decode()

        assert body == "All good"
        assert Message.objects.get(chat=chat, role=Message.Role.ASSISTANT).content == "All good"
