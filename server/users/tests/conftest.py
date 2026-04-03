from rest_framework.test import APIClient
from django.urls import reverse
import pytest


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
def valid_user_payload():
    return {
        "email": "test@example.com",
        "password": "strongpassword123",
        "first_name": "John",
        "last_name": "Doe",
    }


@pytest.fixture
def invalid_user_payload():
    return {
        "email": "test@example.com",
        "password": "123",
    }
