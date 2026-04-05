import pytest
from chats.models import Chat


pytestmark = pytest.mark.django_db


def test_create_chat(auth_client, user):
    old_count = Chat.objects.count()

    response = auth_client.post(
        "/api/chats/",
        {},
        format="json",
    )

    assert response.status_code == 201
    assert Chat.objects.count() - old_count == 1

    chat = Chat.objects.get(uuid=response.data["uuid"])

    assert chat.user == user



def test_list_chats(auth_client, chat):
    response = auth_client.get("/api/chats/")

    assert response.status_code == 200
    assert len(response.data) >= 1

    uuids = [c["uuid"] for c in response.data]
    assert str(chat.uuid) in uuids


def test_retrieve_chat(auth_client, chat):
    response = auth_client.get(f"/api/chats/{chat.uuid}/")

    assert response.status_code == 200
    assert response.data["uuid"] == str(chat.uuid)
    assert response.data["title"] == chat.title


def test_update_chat_title(auth_client, chat):
    response = auth_client.patch(
        f"/api/chats/{chat.uuid}/",
        {"title": "Updated Title"},
        format="json",
    )

    assert response.status_code == 200

    chat.refresh_from_db()
    assert chat.title == "Updated Title"


def test_delete_chat(auth_client, chat):
    old_count = Chat.objects.count()

    response = auth_client.delete(f"/api/chats/{chat.uuid}/")

    assert response.status_code == 204
    assert old_count - Chat.objects.count() == 1


def test_user_cannot_access_other_users_chat(auth_client, another_users_chat):
    response = auth_client.get(f"/api/chats/{another_users_chat.uuid}/")

    assert response.status_code == 404
