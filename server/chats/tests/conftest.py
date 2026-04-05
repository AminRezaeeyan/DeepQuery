from django.urls import reverse
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from chats.models import Chat, Message

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        email="user@test.com",
        password="strongpass123"
    )


@pytest.fixture
def another_user():
    return User.objects.create_user(
        email="another@test.com",
        password="strongpass123"
    )


@pytest.fixture
def jwt_token(api_client, user):
    url = reverse("login")
    response = api_client.post(
        url,
        {
            "email": "user@test.com",
            "password": "strongpass123"
        },
    )

    assert response.status_code == 200
    return response.data["tokens"]["access"]



@pytest.fixture
def auth_client(api_client, jwt_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_token}")
    return api_client


@pytest.fixture
def chat(user):
    return Chat.objects.create(
        user=user,
        title="Test Chat"
    )


@pytest.fixture
def another_users_chat(another_user):
    return Chat.objects.create(
        user=another_user,
        title="Another Chat"
    )


@pytest.fixture
def message(chat):
    return Message.objects.create(
        chat=chat,
        role="user",
        content="hello"
    )
