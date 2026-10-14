import threading

import pytest
from unittest.mock import Mock, patch
from django.db import connection

from ai_core.exceptions import ContextLimitExceededError
from chats.models import Message
from chats.services.chat_service import ChatService
from subscriptions.models import UserUsage
from subscriptions.services import SubscriptionLimitExceeded, SubscriptionService


@pytest.fixture
def generation():
    with patch("chats.services.chat_service.ChatGenerationService") as service_cls, \
         patch("chats.tasks.generate_chat_title.delay"):
        yield service_cls.return_value


def messages_used(user):
    return UserUsage.objects.get(user=user).message_count


def post(client, chat):
    return client.post(f"/api/chats/{chat.uuid}/messages/", {"content": "question"})


def failing_stream(*args, **kwargs):
    yield {"type": "text", "text": "Partial "}
    raise RuntimeError("provider down")


@pytest.mark.django_db
class TestUsageIsCountedOnlyForAnswers:

    def test_a_finished_answer_counts_one_message(self, auth_client, user, chat, generation):
        generation.answer_events.return_value = iter([{"type": "text", "text": "ok"}])

        b"".join(post(auth_client, chat).streaming_content)

        assert messages_used(user) == 1

    def test_a_failed_stream_is_not_counted(self, auth_client, user, chat, generation):
        generation.answer_events.side_effect = failing_stream

        b"".join(post(auth_client, chat).streaming_content)

        assert messages_used(user) == 0

    def test_a_disconnect_mid_answer_is_not_counted(self, chat, generation):
        generation.answer_events.return_value = iter([{"type": "text", "text": "first "}, {"type": "text", "text": "second"}])
        question = Message.objects.create(chat=chat, role=Message.Role.USER, content="question")
        refund = Mock()

        stream = ChatService.generate_stream(chat, question, on_incomplete=refund)
        next(stream)
        stream.close()  # what the server does when the client goes away

        refund.assert_called_once()
        assert not Message.objects.filter(chat=chat, role=Message.Role.ASSISTANT).exists()

    def test_a_request_rejected_before_streaming_is_not_counted(self, auth_client, user, chat, generation):
        generation.prepare.side_effect = ContextLimitExceededError("too large")

        assert post(auth_client, chat).status_code == 400
        assert messages_used(user) == 0


@pytest.mark.django_db(transaction=True)
def test_parallel_requests_cannot_both_take_the_last_message(user):
    SubscriptionService.get_usage(user)
    limit = SubscriptionService.get_user_plan(user).daily_message_limit
    UserUsage.objects.filter(user=user).update(message_count=limit - 1)

    start = threading.Barrier(2)
    outcomes = []

    def attempt():
        start.wait()
        try:
            SubscriptionService.consume(user, "message")
            outcomes.append("ok")
        except SubscriptionLimitExceeded:
            outcomes.append("limited")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["limited", "ok"]
    assert messages_used(user) == limit
