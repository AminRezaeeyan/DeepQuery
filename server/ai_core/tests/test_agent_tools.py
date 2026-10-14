from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from ai_core.agent.citations import SourceRegistry
from ai_core.agent.tools import MAX_OUTPUT_CHARS, ToolContext, relevant_windows, run_tool
from ai_core.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from ai_core.models import EmbeddingProvider
from ai_core.services.embedding_service import EmbeddingService
from chats.models import Chat
from documents.models import Document

PAGES = [{"label": f"p. {n}", "text": f"Page {n} text. " + ("ReFinED 15 89.4" if n == 6 else "")} for n in range(1, 13)]


@pytest.fixture
def context():
    user = get_user_model().objects.create_user(email="agent@example.com", password="violet-harbor-71")
    chat = Chat.objects.create(user=user, title="Research")
    return ToolContext(chat_id=chat.id, user_id=user.id)


def add_document(context, name, segments):
    text = "\n\n".join(s["text"] for s in segments)
    return Document.objects.create(
        chat=Chat.objects.get(id=context.chat_id), user_id=context.user_id, original_filename=name, file=name,
        extracted_text=text, extracted_segments=segments, status="done",
    )


@pytest.fixture
def fake_embeddings():
    EmbeddingProvider.objects.create(name="emb", provider_type="openai", api_key="k", model_name="m", dimension=3, max_tokens=8192)
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]):
        yield


@pytest.mark.django_db
class TestSearchDocuments:

    def test_returns_numbered_passages_with_their_page(self, context, fake_embeddings):
        doc = add_document(context, "refined.pdf", PAGES)
        EmbeddingService().embed_instance(doc, doc.extracted_text, tag=f"chat:{context.chat_id}", segments=PAGES)

        output = run_tool("search_documents", {"query": "ReFinED speed", "limit": 3}, context)
        again = run_tool("search_documents", {"query": "ReFinED speed", "limit": 3}, context)

        assert output.text.startswith("[1] (refined.pdf, p. ")
        assert output.text.count("[") == 3
        assert again.text.split("\n")[0] == output.text.split("\n")[0]  # same passage, same number
        assert output.summary == 'Searched documents for "ReFinED speed" · 3 passages'

    def test_says_when_no_documents_are_attached(self, context):
        assert run_tool("search_documents", {"query": "x"}, context).text == "No documents are attached to this chat."


@pytest.mark.django_db
class TestReadDocument:

    def test_reads_a_page_exactly_and_cites_it(self, context):
        add_document(context, "refined.pdf", PAGES)

        output = run_tool("read_document", {"name": "refined.pdf", "part": "6"}, context)

        assert output.text == "[1] (refined.pdf, p. 6)\nPage 6 text. ReFinED 15 89.4"
        assert output.summary == "Read refined.pdf, p. 6"

    def test_page_ranges_are_capped_at_five_pages(self, context):
        add_document(context, "refined.pdf", PAGES)

        output = run_tool("read_document", {"name": "REFINED.PDF", "part": "p. 2-12"}, context)

        assert [line for line in output.text.split("\n") if line.startswith("[")] == [f"[{i}] (refined.pdf, p. {i + 1})" for i in range(1, 6)]

    def test_reads_a_spreadsheet_sheet_by_name(self, context):
        add_document(context, "runs.xlsx", [{"label": "sheet: runs", "text": "R1 91.5"}, {"label": "sheet: gpu_prices", "text": "T4 0.53"}])

        output = run_tool("read_document", {"name": "runs", "part": "gpu_prices"}, context)

        assert output.text == "[1] (runs.xlsx, sheet: gpu_prices)\nT4 0.53"

    def test_short_documents_come_whole_and_long_ones_list_their_parts(self, context):
        add_document(context, "notes.md", [{"label": None, "text": "Budget: 400 USD"}])
        add_document(context, "long.pdf", [{"label": f"p. {n}", "text": "x" * 3000} for n in range(1, 8)])

        assert run_tool("read_document", {"name": "notes.md"}, context).text == "[1] (notes.md)\nBudget: 400 USD"
        assert "read it in parts. Parts: p. 1, p. 2" in run_tool("read_document", {"name": "long.pdf"}, context).text

    def test_unknown_names_list_the_attached_documents(self, context):
        add_document(context, "refined.pdf", PAGES)

        assert run_tool("read_document", {"name": "blink.pdf"}, context).text == "No document named 'blink.pdf'. Attached documents: refined.pdf."


@pytest.mark.django_db
def test_web_search_numbers_each_result(context):
    with patch("ai_core.agent.tools.WebSearchService") as service:
        service.return_value.search.return_value = [{"title": "Fandom", "url": "https://en.wikipedia.org/wiki/Fandom", "snippet": "Founded in 2004"}]
        output = run_tool("web_search", {"query": "Wikia founded"}, context)

    assert output.text == "[1] Fandom\nhttps://en.wikipedia.org/wiki/Fandom\nFounded in 2004"
    assert context.sources.as_citation_map()[("url", "https://en.wikipedia.org/wiki/Fandom")]["label"] == "https://en.wikipedia.org/wiki/Fandom"


@pytest.mark.django_db
def test_fetch_page_returns_the_parts_matching_the_query(context):
    page = ("filler text " * 200) + "The AIDA CoNLL-YAGO dataset has 1,393 documents. " + ("more filler " * 400)
    with patch("ai_core.agent.tools.WebPageFetcher") as fetcher:
        fetcher.return_value.fetch.return_value = page
        output = run_tool("fetch_page", {"url": "https://example.org/aida", "query": "AIDA documents"}, context)

    assert "1,393 documents" in output.text
    assert output.text.startswith("[1] (https://example.org/aida)")


@pytest.mark.django_db
class TestWikipedia:

    def test_returns_the_best_article(self, context):
        search = MagicMock(json=lambda: {"query": {"search": [{"title": "Tsinghua University"}]}})
        article = MagicMock(json=lambda: {"query": {"pages": {"1": {"extract": "Tsinghua University was established in 1911."}}}})
        with patch("ai_core.agent.tools.requests.get", side_effect=[search, article]) as get, \
             patch("ai_core.agent.tools.check_public_url"):
            output = run_tool("wikipedia", {"query": "Tsinghua founded"}, context)

        assert output.text == "[1] Wikipedia: Tsinghua University (https://en.wikipedia.org/wiki/Tsinghua_University)\nTsinghua University was established in 1911."
        assert all(call.kwargs["timeout"] for call in get.call_args_list)

    @pytest.mark.parametrize("language", ["en.evil.com/x?", "localhost", "EN", ""])
    def test_only_plain_language_codes_are_accepted(self, context, language):
        with patch("ai_core.agent.tools.requests.get") as get:
            output = run_tool("wikipedia", {"query": "x", "language": language}, context)

        assert "must be a Wikipedia code" in output.text
        get.assert_not_called()


@pytest.mark.django_db
class TestRunTool:

    def test_unknown_tools_and_bad_arguments_are_reported_to_the_model(self, context):
        assert run_tool("run_shell", {}, context).text.startswith("Unknown tool 'run_shell'")
        assert run_tool("read_document", {"file": "x"}, context).text.startswith("Wrong arguments for read_document")

    def test_long_outputs_are_cut(self, context):
        add_document(context, "big.md", [{"label": None, "text": "y" * (MAX_OUTPUT_CHARS * 2)}])

        output = run_tool("read_document", {"name": "big.md", "part": "anything"}, context)

        assert len(output.text) < MAX_OUTPUT_CHARS + 200


def test_relevant_windows_keep_reading_order():
    text = "alpha " * 300 + "TARGET one " + "beta " * 600 + "TARGET two " + "gamma " * 300

    result = relevant_windows(text, "target", size=500, top=2)

    assert result.index("TARGET one") < result.index("TARGET two")


def test_the_same_source_keeps_its_number():
    registry = SourceRegistry()

    assert registry.add(("doc", 1, "p. 6"), filename="a.pdf", location="p. 6") == 1
    assert registry.add(("doc", 1, "p. 7"), filename="a.pdf", location="p. 7") == 2
    assert registry.add(("doc", 1, "p. 6"), filename="a.pdf", location="p. 6") == 1
    assert registry.label(2) == "a.pdf, p. 7"
