import importlib

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.urls import reverse

from ai_core.models import LLMProvider

KEY = "sk-live-1234567890abcdef"


def raw_api_key(provider):
    with connection.cursor() as cur:
        cur.execute("SELECT api_key FROM ai_core_llmprovider WHERE id = %s", [provider.id])
        return cur.fetchone()[0]


@pytest.fixture
def provider():
    return LLMProvider.objects.create(name="openai", provider_type="openai", model_name="gpt", api_key=KEY)


@pytest.mark.django_db
class TestApiKeysAreEncrypted:

    def test_database_holds_ciphertext_and_the_model_reads_plain_text(self, provider):
        stored = raw_api_key(provider)

        assert stored.startswith("enc:")
        assert KEY not in stored
        assert LLMProvider.objects.get(pk=provider.pk).api_key == KEY

    def test_keys_written_before_encryption_still_work_and_get_encrypted(self, provider):
        with connection.cursor() as cur:
            cur.execute("UPDATE ai_core_llmprovider SET api_key = %s WHERE id = %s", [KEY, provider.id])

        assert LLMProvider.objects.get(pk=provider.pk).api_key == KEY

        migration = importlib.import_module("ai_core.migrations.0013_encrypt_api_keys")
        migration.encrypt_existing_keys(apps, None)

        assert raw_api_key(provider).startswith("enc:")
        assert LLMProvider.objects.get(pk=provider.pk).api_key == KEY


@pytest.mark.django_db
class TestAdminNeverShowsKeys:

    @pytest.fixture
    def admin_client(self):
        admin = get_user_model().objects.create_superuser(email="admin@example.com", password="password123")
        client = Client()
        client.force_login(admin)
        return client

    def test_change_page_shows_only_the_last_four_characters(self, admin_client, provider):
        page = admin_client.get(reverse("admin:ai_core_llmprovider_change", args=[provider.pk])).content.decode()

        assert KEY not in page
        assert "••••cdef" in page

    def test_saving_with_an_empty_key_keeps_the_current_one(self, admin_client, provider):
        admin_client.post(
            reverse("admin:ai_core_llmprovider_change", args=[provider.pk]),
            {
                "name": "openai renamed",
                "provider_type": "openai",
                "model_name": "gpt",
                "api_key": "",
                "max_context_tokens": provider.max_context_tokens,
            },
        )

        provider.refresh_from_db()
        assert provider.name == "openai renamed"
        assert provider.api_key == KEY
