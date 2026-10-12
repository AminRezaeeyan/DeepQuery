import pytest
from rest_framework import status



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
