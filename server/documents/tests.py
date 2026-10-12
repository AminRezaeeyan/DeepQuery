import os

import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from ai_core.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from ai_core.models import EmbeddedObject, EmbeddingChunk, EmbeddingProvider
from ai_core.services.embedding_service import EmbeddingService
from chats.models import Chat
from documents.models import Document

User = get_user_model()


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def embedding():
    EmbeddingProvider.objects.create(
        name="emb", provider_type="openai", api_key="k", model_name="m", dimension=3, max_tokens=512
    )
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5):
        yield EmbeddingService()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@example.com", password="password123")


@pytest.fixture
def indexed_document(owner, embedding):
    chat = Chat.objects.create(user=owner, title="Research")
    doc = Document.objects.create(
        chat=chat,
        user=owner,
        file=SimpleUploadedFile("notes.txt", b"Solar output rises in the cold."),
        original_filename="notes.txt",
        extracted_text="Solar output rises in the cold.",
        status=Document.StatusChoices.DONE,
    )
    embedding.embed_instance(doc, doc.extracted_text, tag=f"chat:{chat.id}")
    return doc


@pytest.mark.django_db
class TestDeleteDocument:

    def test_deleting_a_document_removes_its_embeddings_and_file(self, owner, indexed_document):
        path = indexed_document.file.path
        client = APIClient()
        client.force_authenticate(owner)

        response = client.delete(f"/api/documents/{indexed_document.uuid}/")

        assert response.status_code == 204
        assert not EmbeddedObject.objects.exists()
        assert not EmbeddingChunk.objects.exists()
        assert not os.path.exists(path)

    def test_chat_search_still_works_after_a_document_is_deleted(self, indexed_document, embedding):
        chat_id = indexed_document.chat.id
        indexed_document.delete()

        assert embedding.search("solar", content_model=Document, tag=f"chat:{chat_id}") == []
