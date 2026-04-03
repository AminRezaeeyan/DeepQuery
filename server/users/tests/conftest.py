from rest_framework.test import APIClient
from django.urls import reverse
import pytest
from ..models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def register_url():
    return reverse('register')


@pytest.fixture
def login_url():
    return reverse('login')

@pytest.fixture
def google_auth_url():
    return reverse('google-auth')


@pytest.fixture
def valid_user_payload():
    return {
        "email": "test@example.com",
        "password": "strongpassword123",
        "first_name": "John",
        "last_name": "Doe",
    }

@pytest.fixture
def existing_user():
    return User.objects.create_user(
        email="existinguser@test.com",
        password="existingpassword"
    )


@pytest.fixture
def invalid_user_payload():
    return {
        "email": "test@example.com",
        "password": "123",
    }
