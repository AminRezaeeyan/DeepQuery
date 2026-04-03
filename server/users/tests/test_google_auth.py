import pytest
from unittest.mock import patch
from users.models import User

@pytest.mark.django_db
class TestGoogleAuth:

    @patch("users.serializers.id_token.verify_oauth2_token")
    def test_google_auth_creates_user(
        self,
        mock_verify,
        api_client,
        google_auth_url
    ):
        mock_verify.return_value = {
            "email": "googleuser@test.com",
            "given_name": "Google",
            "family_name": "User"
        }

        old_users_count = User.objects.count() 
        response = api_client.post(
            google_auth_url,
            {"token": "fake-token"},
            format="json"
        )

        assert response.status_code == 200
        assert User.objects.count() - old_users_count == 1
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert response.data["tokens"]["token_type"] == "Bearer"

    
    @patch("users.serializers.id_token.verify_oauth2_token")
    def test_google_auth_existing_user(
        self,
        mock_verify,
        api_client,
        google_auth_url,
        existing_user
    ):
        mock_verify.return_value = {
            "email": "existinguser@test.com",
            "given_name": "Google",
            "family_name": "User"
        }

        old_users_count = User.objects.count()
        response = api_client.post(
            google_auth_url,
            {"token": "fake-token"},
            format="json"
        )
        final_count = User.objects.count()

        assert response.status_code == 200
        assert final_count == old_users_count
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert response.data["tokens"]["token_type"] == "Bearer"


    @patch("users.serializers.id_token.verify_oauth2_token")
    def test_google_auth_invalid_token(
        self,
        mock_verify,
        api_client,
        google_auth_url
    ):
        mock_verify.side_effect = Exception("Invalid token")

        response = api_client.post(
            google_auth_url,
            {"id_token": "bad-token"},
            format="json"
        )

        assert response.status_code == 400