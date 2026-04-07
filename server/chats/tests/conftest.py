import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from chats.models import Chat, Message

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user():
    return User.objects.create_user(email="test@example.com", password="password")

@pytest.fixture
def other_user():
    return User.objects.create_user(email="other@example.com", password="password")

@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture
def chat(user):
    return Chat.objects.create(user=user, provider_id=1, title="Test Chat")

@pytest.fixture
def mock_default_provider():
    with patch("ai_core.services.provider_service.ProviderService.get_default_provider_id", return_value=1) as mock:
        yield mock

@pytest.fixture
def populated_chat(chat):
    # Creating a sequence of messages
    msg1 = Message.objects.create(chat=chat, role=Message.Role.USER, content="First question")
    msg2 = Message.objects.create(chat=chat, role=Message.Role.ASSISTANT, content="First answer")
    msg3 = Message.objects.create(chat=chat, role=Message.Role.USER, content="Second question")
    msg4 = Message.objects.create(chat=chat, role=Message.Role.ASSISTANT, content="Second answer")
    
    return {
        "chat": chat,
        "first_user_msg": msg1,
        "first_assistant_msg": msg2,
        "last_user_msg": msg3,
        "last_assistant_msg": msg4
    }
