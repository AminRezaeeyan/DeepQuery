import pytest
from unittest.mock import patch
from chats.models import Message


pytestmark = pytest.mark.django_db

class FakeChatService:
    def __init__(self, *args, **kwargs):
        pass

    def stream_answer(self, *args, **kwargs):
        yield "Hello"
        yield " world"



def test_create_message(auth_client, chat):
    from unittest.mock import patch
    from chats.models import Message

    old_count = Message.objects.count()

    with patch("chats.views.ChatService", FakeChatService):
        response = auth_client.post(
            f"/api/chats/{chat.uuid}/messages/",
            {
                "content": "Hello AI"
            },
            format="json",
        )
    list(response.streaming_content)
    assert response.status_code == 200
    assert Message.objects.count() == old_count + 2


def test_list_chat_messages(auth_client, message, chat):
    response = auth_client.get(f"/api/chats/{chat.uuid}/messages/")

    assert response.status_code == 200

    uuids = [m["uuid"] for m in response.data]
    assert str(message.uuid) in uuids


def test_retrieve_message(auth_client, message):
    response = auth_client.get(f"/api/messages/{message.uuid}/")

    assert response.status_code == 200
    assert response.data["uuid"] == str(message.uuid)
    assert response.data["content"] == message.content


def test_update_message(auth_client, message):
    response = auth_client.patch(
        f"/api/messages/{message.uuid}/",
        {"content": "Edited message"},
        format="json",
    )

    assert response.status_code == 200

    message.refresh_from_db()
    assert message.content == "Edited message"


def test_user_cannot_access_other_users_message(auth_client, another_users_chat):
    message = Message.objects.create(
        chat=another_users_chat,
        role="user",
        content="private"
    )

    response = auth_client.get(f"/api/messages/{message.uuid}/")

    assert response.status_code == 404
