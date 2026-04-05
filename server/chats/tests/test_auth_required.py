import pytest


pytestmark = pytest.mark.django_db


def test_chat_requires_auth(api_client):
    response = api_client.get("/api/chats/")
    assert response.status_code == 401


def test_message_requires_auth(api_client, message):
    response = api_client.get(f"/api/messages/{message.uuid}/")
    assert response.status_code == 401
