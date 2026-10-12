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


@pytest.mark.django_db
class TestUploadValidation:

    @pytest.fixture
    def client(self, owner):
        client = APIClient()
        client.force_authenticate(owner)
        return client

    @pytest.fixture
    def chat(self, owner):
        return Chat.objects.create(user=owner, title="Mine")

    def upload(self, client, chat, name, content):
        with patch("documents.views.extract_and_index_document.delay"):
            return client.post("/api/documents/", {"chat": str(chat.uuid), "file": SimpleUploadedFile(name, content)}, format="multipart")

    def test_cannot_upload_into_another_users_chat(self, client):
        stranger = User.objects.create_user(email="stranger@example.com", password="password123")
        their_chat = Chat.objects.create(user=stranger, title="Theirs")

        response = self.upload(client, their_chat, "notes.txt", b"hello")

        assert response.status_code == 400
        assert not Document.objects.exists()

    def test_rejects_files_over_the_size_limit(self, client, chat, settings):
        settings.DOCUMENT_MAX_UPLOAD_BYTES = 10

        response = self.upload(client, chat, "notes.txt", b"x" * 11)

        assert response.status_code == 400

    @pytest.mark.parametrize(
        "name, content",
        [("report.pdf", b"MZ\x90\x00 an executable"), ("sheet.xlsx", b"not a zip"), ("notes.txt", b"\x00\x01binary\x00")],
    )
    def test_rejects_content_that_does_not_match_the_extension(self, client, chat, name, content):
        assert self.upload(client, chat, name, content).status_code == 400

    @pytest.mark.parametrize(
        "name, content",
        [("report.pdf", b"%PDF-1.7\n..."), ("notes.md", "# یادداشت\nمتن فارسی".encode()), ("data.csv", b"a,b\n1,2\n")],
    )
    def test_accepts_matching_files(self, client, chat, name, content):
        assert self.upload(client, chat, name, content).status_code == 201
