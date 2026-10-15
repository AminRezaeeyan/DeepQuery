from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management import call_command

from ai_core.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from ai_core.models import EmbeddingChunk, EmbeddingProvider
from ai_core.services.chat_service import ChatGenerationService
from chats.models import Chat
from documents.models import Document
from documents.tasks import extract_and_index_document
from evaluation.grading import source_of

PAPER = Path(__file__).resolve().parents[1].parent / "eval" / "sources" / "refined.pdf"


@pytest.fixture
def indexed_paper(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    EmbeddingProvider.objects.create(name="emb", provider_type="openai", api_key="k", model_name="m", dimension=3, max_tokens=8192)
    user = get_user_model().objects.create_user(email="reader@example.com", password="violet-harbor-71")
    chat = Chat.objects.create(user=user, title="Papers")
    with open(PAPER, "rb") as f:
        doc = Document.objects.create(chat=chat, user=user, original_filename="refined.pdf", file=File(f, name="refined.pdf"))
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]):
        extract_and_index_document(doc.id)
    doc.refresh_from_db()
    return chat, doc


@pytest.mark.django_db
class TestPageLevelChunks:

    def test_every_chunk_knows_its_page(self, indexed_paper):
        _, doc = indexed_paper
        chunks = EmbeddingChunk.objects.filter(embedded_object__object_id=str(doc.pk))

        assert chunks.count() > 20
        assert set(chunks.values_list("location", flat=True)) == {f"p. {n}" for n in range(1, 13)}
        assert chunks.filter(location="p. 6", text__contains="ReFinED 15 89.4").exists()
        assert len(doc.extracted_segments) == 12

    def test_reindexing_rebuilds_the_chunks(self, indexed_paper):
        _, doc = indexed_paper
        EmbeddingChunk.objects.filter(embedded_object__object_id=str(doc.pk)).update(location="")

        with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]):
            call_command("reindex_documents")

        assert not EmbeddingChunk.objects.filter(embedded_object__object_id=str(doc.pk), location="").exists()


@pytest.mark.django_db
def test_citations_name_the_page():
    doc = Document(id=1, original_filename="refined.pdf")
    other = Document(id=2, original_filename="blink.pdf")
    results = [
        (doc, 0.9, "ReFinED 15 89.4", "p. 6"),
        (doc, 0.8, "more of table 5", "p. 6"),
        (doc, 0.7, "deployment details", "p. 7"),
        (other, 0.6, "9.2 ms per query", "p. 7"),
    ]
    with patch("ai_core.services.chat_service.LLMService") as llm, \
         patch("ai_core.services.chat_service.LongTermMemoryService"), \
         patch("ai_core.services.chat_service.WebKnowledgeService"), \
         patch("ai_core.services.chat_service.DocumentRAGService") as rag:
        llm.return_value.provider_config.max_context_tokens = 128000
        llm.return_value.provider.supports_tools = False  # the single-pass pipeline
        llm.return_value.stream.return_value = iter(["Answer [1]."])
        rag.return_value.build_knowledge_context.return_value = ("", results)
        service = ChatGenerationService(1, 1, is_temporary=True)
        prepared = service.prepare("How fast is ReFinED?")
        output = "".join(service.stream_prepared(prepared))

    sources = prepared["messages"][-1]["content"]
    assert "--- Source [1] (refined.pdf, p. 6) ---\nReFinED 15 89.4" in sources
    assert "--- Source [1] (refined.pdf, p. 6) ---\nmore of table 5" in sources  # same page, same number
    assert "--- Source [3] (blink.pdf, p. 7) ---" in sources
    # Only the cited source is listed, under its own number.
    assert output.endswith("**References:**\n[1] refined.pdf, p. 6\n")


def test_eval_counts_a_page_citation_as_citing_the_file():
    assert source_of("refined.pdf, p. 6") == "refined.pdf"
    assert source_of("reproduction_runs.xlsx, sheet: gpu_prices") == "reproduction_runs.xlsx"
    assert source_of("https://example.org/a, b") == "https://example.org/a, b"


@pytest.mark.django_db
def test_references_list_only_the_cited_sources_with_their_numbers():
    pages = [(Document(id=1, original_filename="refined.pdf"), 0.9 - n / 100, f"page {n} text", f"p. {n}") for n in range(1, 13)]
    with patch("ai_core.services.chat_service.LLMService") as llm, \
         patch("ai_core.services.chat_service.LongTermMemoryService"), \
         patch("ai_core.services.chat_service.WebKnowledgeService"), \
         patch("ai_core.services.chat_service.DocumentRAGService") as rag:
        llm.return_value.provider_config.max_context_tokens = 128000
        llm.return_value.provider.supports_tools = False  # the single-pass pipeline
        rag.return_value.build_knowledge_context.return_value = ("", pages)
        service = ChatGenerationService(1, 1, is_temporary=True)

        llm.return_value.stream.return_value = iter(["Fast [3], ", "accurate [7][3]."])
        cited = "".join(service.stream_prepared(service.prepare("q")))

        llm.return_value.stream.return_value = iter(["No citations here."])
        uncited = "".join(service.stream_prepared(service.prepare("q")))

    assert cited.endswith("**References:**\n[3] refined.pdf, p. 3\n[7] refined.pdf, p. 7\n")
    assert "References" not in uncited
