import pytest
from unittest.mock import patch
from rest_framework.permissions import IsAuthenticated
from rest_framework.settings import api_settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from users.models import User


def test_endpoints_require_sign_in_by_default():
    assert api_settings.DEFAULT_PERMISSION_CLASSES == [IsAuthenticated]


@pytest.mark.django_db
class TestPublicEndpointsStayPublic:

    def test_plans(self):
        assert APIClient().get("/api/subscriptions/plans/").status_code == 200

    def test_api_schema(self):
        assert APIClient().get("/api/schema/").status_code == 200


@pytest.mark.django_db
class TestSignInIsRateLimited:

    def test_too_many_login_attempts_are_refused(self):
        client = APIClient()
        with patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"auth": "3/minute"}):
            codes = [
                client.post("/auth/login/", {"email": "victim@example.com", "password": f"guess-{i}-xyz"}, format="json").status_code
                for i in range(4)
            ]

        assert codes[:3] == [400, 400, 400]
        assert codes[3] == 429


@pytest.mark.django_db
class TestPasswordValidators:

    @pytest.mark.parametrize("password", ["password123", "12345678", "short1", "reader@example.com"])
    def test_weak_passwords_are_rejected(self, password):
        response = APIClient().post("/auth/register/", {"email": "reader@example.com", "password": password}, format="json")

        assert response.status_code == 400
        assert "password" in response.json()
        assert not User.objects.filter(email="reader@example.com").exists()

    def test_strong_password_is_accepted(self):
        response = APIClient().post("/auth/register/", {"email": "reader@example.com", "password": "violet-harbor-71"}, format="json")

        assert response.status_code == 201
