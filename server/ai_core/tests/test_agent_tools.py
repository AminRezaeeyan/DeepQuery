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

    def test_a_page_range_comes_whole_when_it_fits(self, context):
        add_document(context, "refined.pdf", PAGES)

        output = run_tool("read_document", {"name": "REFINED.PDF", "part": "p. 2-12"}, context)

        assert [line for line in output.text.split("\n") if line.startswith("[")] == [f"[{i}] (refined.pdf, p. {i + 1})" for i in range(1, 12)]

    def test_a_long_range_stops_at_a_page_boundary_and_says_where_to_continue(self, context):
        add_document(context, "paper.pdf", [{"label": f"p. {n}", "text": f"Page {n} " + "x" * 5000} for n in range(1, 13)])

        output = run_tool("read_document", {"name": "paper.pdf", "part": "1-12"}, context)

        assert "[cut" not in output.text  # nothing is cut mid-page
        assert output.text.endswith("[Shown: p. 1, p. 2. Not shown yet: p. 3-12; read them with part='3-12'.]")
        again = run_tool("read_document", {"name": "paper.pdf", "part": "11-12"}, context)
        assert "Not shown yet" not in again.text and "Page 12" in again.text

    def test_reads_a_spreadsheet_sheet_by_name(self, context):
        add_document(context, "runs.xlsx", [{"label": "sheet: runs", "text": "R1 91.5"}, {"label": "sheet: gpu_prices", "text": "T4 0.53"}])

        output = run_tool("read_document", {"name": "runs", "part": "gpu_prices"}, context)

        assert output.text == "[1] (runs.xlsx, sheet: gpu_prices)\nT4 0.53"

    def test_short_documents_come_whole_and_long_ones_list_their_parts(self, context):
        add_document(context, "notes.md", [{"label": None, "text": "Budget: 400 USD"}])
        add_document(context, "long.pdf", [{"label": f"p. {n}", "text": "x" * 3000} for n in range(1, 8)])

        assert run_tool("read_document", {"name": "notes.md"}, context).text == "[1] (notes.md)\nBudget: 400 USD"
        assert "read it in parts. Parts: p. 1, p. 2" in run_tool("read_document", {"name": "long.pdf"}, context).text

    def test_a_long_file_without_pages_shows_its_start_and_points_to_run_python(self, context):
        rows = "\n".join(f"m{i},NIL,NIL" for i in range(2000))
        add_document(context, "nil_audit.csv", [{"label": None, "text": "mention,gold,cross_pred\n" + rows}])

        output = run_tool("read_document", {"name": "nil_audit.csv"}, context)

        assert output.text.startswith("[1] (nil_audit.csv)\nmention,gold,cross_pred\nm0,NIL,NIL")
        assert "of 2001. Use run_python to work with the whole file" in output.text
        assert "Parts:" not in output.text
        assert output.summary == "Read the start of nil_audit.csv"

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


SOSA_SECTIONS = [
    {"index": "1", "line": "Life", "toclevel": 1},
    {"index": "5", "line": "Discography", "toclevel": 1},
    {"index": "6", "line": "Studio albums", "toclevel": 2},
]
STUDIO_HTML = """<h3>Studio albums</h3><table><tr><th>Year</th><th>Album</th></tr>
<tr><td>2005</td><td>Corazón Libre<sup class="reference">[3]</sup></td></tr>
<tr><td>2009</td><td>Cantora 1</td></tr></table>"""


def fake_wikipedia(calls):
    def get(url, params, headers, timeout):
        calls.append(params)
        if params.get("list") == "search":
            data = {"query": {"search": [{"title": "Mercedes Sosa"}, {"title": "Cantora, un Viaje Íntimo"}]}}
        elif params.get("prop") == "revisions":
            data = {"query": {"pages": {"1": {"revisions": [{"revid": 1126540422, "timestamp": "2022-12-09T22:29:41Z"}]}}}}
        elif params.get("prop") == "sections":
            data = {"parse": {"sections": SOSA_SECTIONS}}
        elif params.get("section") == "0":
            data = {"parse": {"text": {"*": "<p>Mercedes Sosa was an Argentine singer.</p>"}}}
        else:
            data = {"parse": {"text": {"*": STUDIO_HTML}}}
        return MagicMock(json=lambda: data)
    return get


@pytest.mark.django_db
class TestWikipedia:

    def test_reads_the_section_the_question_is_about_with_its_table(self, context):
        calls = []
        with patch("ai_core.agent.tools.requests.get", side_effect=fake_wikipedia(calls)), \
             patch("ai_core.agent.tools.check_public_url"):
            output = run_tool("wikipedia", {"query": "Mercedes Sosa studio albums", "as_of": "2022"}, context)

        assert "2005 | Corazón Libre" in output.text  # table rows stay together, citation markers gone
        assert "2009 | Cantora 1" in output.text
        assert "Mercedes Sosa was an Argentine singer." in output.text
        assert output.text.startswith("[1] Wikipedia: Mercedes Sosa (revision of 2022-12-09) https://en.wikipedia.org/w/index.php?oldid=1126540422")
        assert "Other matching articles: Cantora, un Viaje Íntimo" in output.text
        revision = next(c for c in calls if c.get("prop") == "revisions")
        assert revision["rvstart"] == "2022-12-31T23:59:59Z" and revision["rvdir"] == "older"
        assert output.summary == "Read Wikipedia: Mercedes Sosa, Studio albums (as of 2022)"

    def test_a_named_section_is_read(self, context):
        calls = []
        with patch("ai_core.agent.tools.requests.get", side_effect=fake_wikipedia(calls)), \
             patch("ai_core.agent.tools.check_public_url"):
            run_tool("wikipedia", {"query": "Mercedes Sosa", "section": "studio albums"}, context)

        assert [c["section"] for c in calls if "section" in c] == ["0", "6"]

    @pytest.mark.parametrize("arguments", [{"language": "en.evil.com/x?"}, {"language": "localhost"}, {"language": "EN"}, {"as_of": "last year"}])
    def test_rejects_unsafe_or_malformed_arguments(self, context, arguments):
        with patch("ai_core.agent.tools.requests.get") as get:
            output = run_tool("wikipedia", {"query": "x", **arguments}, context)

        assert "must be" in output.text
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


@pytest.mark.django_db
class TestFindText:

    def test_finds_every_line_with_all_the_words_and_cites_its_page(self, context):
        add_document(context, "refined.pdf", [
            {"label": "p. 3", "text": "We use fine-grained entity types\nfrom Wikidata."},
            {"label": "p. 11", "text": "Hyperparameter Value\n# candidates 30\n# entity types 1400\nmention transformer init. roberta-base"},
        ])

        output = run_tool("find_text", {"text": "Entity Types"}, context)

        assert output.text.splitlines() == [
            "[1] (refined.pdf, p. 3) We use fine-grained entity types / from Wikidata.",
            "[2] (refined.pdf, p. 11) # candidates 30 / # entity types 1400 / mention transformer init. roberta-base",
        ]
        assert output.summary == 'Found "Entity Types" · 2 lines'

    def test_says_plainly_when_nothing_matches(self, context):
        add_document(context, "refined.pdf", PAGES)

        assert run_tool("find_text", {"text": "inter-annotator", "name": "refined"}, context).text == \
            "No line in refined contains all of: inter, annotator."

    def test_matches_persian_across_letter_forms(self, context):
        add_document(context, "notes.md", [{"label": None, "text": "بودجه: ۴۰۰ دلار\nکتابخانه ملی"}])

        assert "کتابخانه ملی" in run_tool("find_text", {"text": "كتابخانه"}, context).text


def test_a_spreadsheet_gets_one_number_that_names_the_sheets_read():
    registry = SourceRegistry()

    runs = registry.add(("doc", 2, "sheet: runs"), filename="runs.xlsx", location="sheet: runs")
    notes = registry.add(("doc", 2, "sheet: notes"), filename="runs.xlsx", location="sheet: notes")
    whole = registry.add(("doc", 2, ""), filename="runs.xlsx")  # e.g. run_python on the whole file

    assert runs == notes == whole == 1
    assert registry.label(1) == "runs.xlsx (sheets: runs, notes)"
    # Tool results still say which sheet they show.
    assert registry.header(1, "sheet: notes") == "[1] (runs.xlsx, sheet: notes)"


def test_text_files_get_one_number_and_pdf_pages_keep_their_own():
    registry = SourceRegistry()

    assert registry.add(("doc", 1, ""), filename="notes.md") == 1
    assert registry.add(("doc", 1, ""), filename="notes.md") == 1
    assert registry.add(("doc", 3, "p. 6"), filename="refined.pdf", location="p. 6") == 2
    assert registry.add(("doc", 3, "p. 7"), filename="refined.pdf", location="p. 7") == 3


@pytest.mark.django_db
def test_asking_for_a_page_of_a_file_without_pages_reads_the_file(context):
    add_document(context, "lab_notes.md", [{"label": None, "text": "Budget: 400 USD"}])

    output = run_tool("read_document", {"name": "lab_notes.md", "part": "1"}, context)

    assert output.text == "[1] (lab_notes.md)\nBudget: 400 USD"
