import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from chats.models import Chat, Message

User = get_user_model()


@pytest.fixture
def admin_client():
    admin = User.objects.create_superuser(email="admin@example.com", password="password123")
    client = Client()
    client.force_login(admin)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize(
    "changelist",
    [
        "admin:chats_chat_changelist",
        "admin:ai_core_memoryfact_changelist",
        "admin:subscriptions_usersubscription_changelist",
        "admin:subscriptions_userusage_changelist",
        "admin:subscriptions_payment_changelist",
    ],
)
def test_admin_search_by_user_works(admin_client, changelist):
    # The User model has no username field; searching on it raised FieldError.
    response = admin_client.get(reverse(changelist), {"q": "someone@example.com"})

    assert response.status_code == 200


@pytest.mark.django_db
class TestRestoreChats:

    def test_restore_brings_back_the_chat_and_its_messages(self, chat):
        question = Message.objects.create(chat=chat, role=Message.Role.USER, content="Q")
        answer = Message.objects.create(chat=chat, role=Message.Role.ASSISTANT, content="A")
        chat.mark_deleted()

        chat.restore()

        assert Chat.objects.filter(pk=chat.pk).exists()
        assert set(Message.objects.filter(chat=chat)) == {question, answer}

    def test_restore_keeps_messages_replaced_by_an_edit_hidden(self, chat):
        old_question = Message.objects.create(chat=chat, role=Message.Role.USER, content="old")
        old_answer = Message.objects.create(chat=chat, role=Message.Role.ASSISTANT, content="old answer")
        old_question.mark_edited()
        old_answer.mark_deleted()
        new_question = Message.objects.create(chat=chat, role=Message.Role.USER, content="new")
        new_answer = Message.objects.create(chat=chat, role=Message.Role.ASSISTANT, content="new answer")
        chat.mark_deleted()

        chat.restore()

        assert list(Message.objects.filter(chat=chat).order_by("created_at")) == [new_question, new_answer]

    def test_admin_action_can_reach_deleted_chats(self, admin_client, chat):
        Message.objects.create(chat=chat, role=Message.Role.USER, content="Q")
        chat.mark_deleted()

        response = admin_client.post(
            reverse("admin:chats_chat_changelist"),
            {"action": "restore_chats", "_selected_action": [chat.pk]},
        )

        assert response.status_code == 302
        chat.refresh_from_db()
        assert not chat.is_deleted
        assert Message.objects.filter(chat=chat).count() == 1
