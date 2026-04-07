import pytest
from unittest.mock import patch
from rest_framework import status

from chats.models import Message


class MockChatGenerationService:
    def __init__(self, provider_id=None):
        self.provider_id = provider_id

    def stream_answer(self, content):
        yield "Edited "
        yield "fake "
        yield "response!"


@pytest.mark.django_db
class TestRetrieveMessage:

    def test_retrieve_own_message(self, auth_client, populated_chat):
        msg = populated_chat["first_user_msg"]
        
        response = auth_client.get(f"/api/messages/{msg.uuid}/")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["content"] == "First question"

    def test_cannot_retrieve_others_message(self, api_client, other_user, populated_chat):
        api_client.force_authenticate(user=other_user)
        msg = populated_chat["first_user_msg"]
        
        response = api_client.get(f"/api/messages/{msg.uuid}/")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestUpdateMessage:

    @patch("chats.services.chat_service.ChatGenerationService", new=MockChatGenerationService)
    def test_update_last_user_message_success(self, auth_client, populated_chat):
        msg_to_edit = populated_chat["last_user_msg"]
        assistant_to_delete = populated_chat["last_assistant_msg"]
        
        response = auth_client.patch(
            f"/api/messages/{msg_to_edit.uuid}/", 
            {"content": "Edited second question"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        stream_content = b"".join(response.streaming_content).decode("utf-8")
        assert stream_content == "Edited fake response!"
        
        msg_to_edit.refresh_from_db()
        assistant_to_delete.refresh_from_db()
        
        # 1. Old message marked as edited (soft deleted)
        assert msg_to_edit.is_deleted is True
        assert msg_to_edit.edited_at is not None
        
        # 2. Previous assistant response soft deleted
        assert assistant_to_delete.is_deleted is True
        
        # 3. New user message and assistant message generated in DB
        chat = populated_chat["chat"]
        new_user_msg = Message.objects.filter(chat=chat, role=Message.Role.USER).first()
        new_assistant_msg = Message.objects.filter(chat=chat, role=Message.Role.ASSISTANT).first()
        
        assert new_user_msg.content == "Edited second question"
        assert new_assistant_msg.content == "Edited fake response!"

    def test_update_non_last_user_message_fails(self, auth_client, populated_chat):
        msg_to_edit = populated_chat["first_user_msg"]
        
        response = auth_client.patch(
            f"/api/messages/{msg_to_edit.uuid}/", 
            {"content": "Edited first question"}
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only the last user message can be edited" in str(response.data)

    def test_update_assistant_message_fails(self, auth_client, populated_chat):
        msg_to_edit = populated_chat["last_assistant_msg"]
        
        response = auth_client.patch(
            f"/api/messages/{msg_to_edit.uuid}/", 
            {"content": "Trying to edit AI"}
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only user messages can be edited" in str(response.data)
