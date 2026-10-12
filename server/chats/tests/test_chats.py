import pytest
from unittest.mock import patch
from rest_framework import status

from chats.models import Chat, Message
from ai_core.exceptions import ProviderUnavailable


@pytest.mark.django_db
class TestListChats:
    
    def test_list_returns_only_user_chats(self, auth_client, user, other_user):
        Chat.objects.create(user=user, title="User Chat")
        Chat.objects.create(user=other_user, title="Other Chat")

        response = auth_client.get("/api/chats/")
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "User Chat"


@pytest.mark.django_db
class TestCreateChat:

    def test_creates_new_chat_if_none_empty(self, auth_client, user, mock_default_provider):
        response = auth_client.post("/api/chats/")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Chat.objects.filter(user=user).count() == 1
        assert response.data["provider_id"] == 1

    def test_reuses_existing_empty_chat(self, auth_client, user, mock_default_provider):
        existing_chat = Chat.objects.create(user=user, provider_id=1)
        
        response = auth_client.post("/api/chats/")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["uuid"] == str(existing_chat.uuid)
        assert Chat.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestUpdateChat:

    @patch("ai_core.services.provider_service.ProviderService.validate_chat_provider_id")
    def test_update_title_success(self, mock_validate, auth_client, chat):
        response = auth_client.patch(f"/api/chats/{chat.uuid}/", {"title": "Updated Title"})
        
        assert response.status_code == status.HTTP_200_OK
        chat.refresh_from_db()
        assert chat.title == "Updated Title"

    @patch("ai_core.services.provider_service.ProviderService.validate_chat_provider_id")
    def test_update_provider_without_messages(self, mock_validate, auth_client, chat):
        response = auth_client.patch(f"/api/chats/{chat.uuid}/", {"provider_id": 2})
        
        assert response.status_code == status.HTTP_200_OK
        chat.refresh_from_db()
        assert chat.provider_id == 2

    def test_update_provider_with_messages_fails(self, auth_client, chat):
        Message.objects.create(chat=chat, role=Message.Role.USER, content="Hello")
        
        response = auth_client.patch(f"/api/chats/{chat.uuid}/", {"provider_id": 2})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Provider cannot be changed" in str(response.data)

    @patch("ai_core.services.provider_service.ProviderService.validate_chat_provider_id")
    def test_update_with_invalid_provider_fails(self, mock_validate, auth_client, chat):
        mock_validate.side_effect = ProviderUnavailable("Invalid provider")
        
        response = auth_client.patch(f"/api/chats/{chat.uuid}/", {"provider_id": 999})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDeleteChat:

    def test_soft_deletes_chat_and_messages(self, auth_client, chat):
        msg = Message.objects.create(chat=chat, role=Message.Role.USER, content="Hello")
        
        response = auth_client.delete(f"/api/chats/{chat.uuid}/")
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        chat.refresh_from_db()
        msg.refresh_from_db()
        
        assert chat.is_deleted is True
        assert chat.deleted_at is not None
        assert msg.is_deleted is True
