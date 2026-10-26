import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestTokenRefresh:

    def test_refresh_token_from_login_gets_a_new_access_token(self):
        User.objects.create_user(email="reader@example.com", password="password123")
        client = APIClient()
        tokens = client.post("/auth/login/", {"email": "reader@example.com", "password": "password123"}, format="json").data["tokens"]

        response = client.post("/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")

        assert response.status_code == 200
        assert response.data["access"]
        authed = APIClient()
        authed.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        assert authed.get("/api/chats/").status_code == 200

    def test_invalid_refresh_token_is_rejected(self):
        response = APIClient().post("/auth/token/refresh/", {"refresh": "not-a-token"}, format="json")

        assert response.status_code == 401
