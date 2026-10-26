import pytest
from unittest.mock import patch

from ai_core.services.memory.short_term_memory import ShortTermMemory
from chats.models import Message
from chats.services.chat_service import ChatService


@pytest.mark.django_db
class TestCurrentQuestionIsSentOnce:

    @pytest.fixture
    def conversation(self, chat):
        Message.objects.create(chat=chat, role=Message.Role.USER, content="earlier question")
        Message.objects.create(chat=chat, role=Message.Role.ASSISTANT, content="earlier answer")
        current = Message.objects.create(chat=chat, role=Message.Role.USER, content="current question")
        return chat, current

    def test_history_stops_before_the_current_question(self, conversation):
        chat, current = conversation

        history = ShortTermMemory(chat.id, token_limit=10_000, before=current.created_at).collect()

        assert [m["content"] for m in history] == ["earlier question", "earlier answer"]

    def test_generate_stream_collects_history_before_the_saved_question(self, conversation):
        chat, current = conversation

        with patch("chats.services.chat_service.ChatGenerationService") as service_cls:
            service_cls.return_value.answer_events.return_value = iter([{"type": "text", "text": "ok"}])
            list(ChatService.generate_stream(chat, current))

        call = service_cls.return_value.prepare.call_args
        assert call.kwargs["history_before"] == current.created_at
