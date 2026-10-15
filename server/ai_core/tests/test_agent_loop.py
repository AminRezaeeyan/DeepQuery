import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from ai_core.agent.loop import ResearchAgent
from ai_core.agent.tools import ToolContext, tool_definitions
from ai_core.llm_providers.base import ToolCall
from ai_core.models import AITaskConfig, LLMProvider
from ai_core.services.chat_service import ChatGenerationService
from chats.models import Chat, Message
from documents.models import Document

PAGES = [{"label": f"p. {n}", "text": f"Page {n}." + (" ReFinED 15 89.4" if n == 6 else "")} for n in range(1, 8)]


class ScriptedModel:
    """A fake tool-calling model: each turn plays the next scripted list of events."""

    supports_tools = True

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls = []

    def stream_turn(self, messages, tools, tool_choice="auto", reasoning_effort=None):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": [t["name"] for t in tools], "tool_choice": tool_choice,
                           "reasoning_effort": reasoning_effort})
        yield from self.turns.pop(0)


def read_page_6():
    return [("text", "Let me check the table."), ("tool_calls", [ToolCall("call_1", "read_document", {"name": "refined.pdf", "part": "6"})])]


@pytest.fixture
def context():
    user = get_user_model().objects.create_user(email="agent@example.com", password="violet-harbor-71")
    chat = Chat.objects.create(user=user, title="Research")
    Document.objects.create(chat=chat, user=user, original_filename="refined.pdf", file="refined.pdf",
                            extracted_text="...", extracted_segments=PAGES, status="done")
    return ToolContext(chat_id=chat.id, user_id=user.id)


def run(agent, messages):
    return list(agent.run(messages))


@pytest.mark.django_db
class TestResearchAgent:

    def test_calls_a_tool_then_answers_from_its_result(self, context):
        model = ScriptedModel(read_page_6(), [("text", "ReFinED takes 15 s [1].")])
        agent = ResearchAgent(model, context, tool_definitions(web=False), max_steps=8, token_budget=100_000)
        messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": "How fast is ReFinED?"}]

        events = run(agent, messages)

        # The short preamble before the tool call never reaches the user.
        assert [e["type"] for e in events] == ["step", "step", "text"]
        assert events[0] == {"type": "step", "id": 1, "tool": "read_document", "arguments": {"name": "refined.pdf", "part": "6"},
                             "status": "running", "summary": "Reading refined.pdf, p. 6"}
        assert events[1]["summary"] == "Read refined.pdf, p. 6"
        assert events[1]["output"] == "[1] (refined.pdf, p. 6)\nPage 6. ReFinED 15 89.4"
        assert agent.answer == "ReFinED takes 15 s [1]."
        # The model saw its own tool call and the tool's result before answering.
        assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
        assert messages[3] == {"role": "tool", "tool_call_id": "call_1", "content": "[1] (refined.pdf, p. 6)\nPage 6. ReFinED 15 89.4"}

    def test_the_last_step_must_answer_without_tools(self, context):
        model = ScriptedModel(read_page_6(), read_page_6(), [("text", "Best answer I have.")])
        agent = ResearchAgent(model, context, tool_definitions(web=False), max_steps=2, token_budget=100_000)

        run(agent, [{"role": "user", "content": "q"}])

        assert [c["tool_choice"] for c in model.calls] == ["auto", "auto", "none"]
        assert agent.answer == "Best answer I have."

    def test_a_full_context_forces_an_answer(self, context):
        model = ScriptedModel([("text", "Answer now.")])
        agent = ResearchAgent(model, context, tool_definitions(web=False), max_steps=8, token_budget=10)

        run(agent, [{"role": "user", "content": "a question longer than ten tokens, which fills the budget at once"}])

        assert model.calls[0]["tool_choice"] == "none"

    def test_invalid_arguments_go_back_to_the_model(self, context):
        bad = [("tool_calls", [ToolCall.from_raw("c1", "read_document", '{"name": ')])]
        model = ScriptedModel(bad, [("text", "Sorry.")])
        messages = [{"role": "user", "content": "q"}]

        run(ResearchAgent(model, context, tool_definitions(web=False), max_steps=8, token_budget=100_000), messages)

        assert messages[-1]["role"] == "tool" and messages[-1]["content"].startswith("Invalid arguments")


def test_web_tools_are_offered_only_with_web_search_on():
    assert {t["name"] for t in tool_definitions(web=False)} == {"search_documents", "read_document", "find_text", "run_python"}
    assert {"web_search", "fetch_page", "wikipedia"} <= {t["name"] for t in tool_definitions(web=True)}


@pytest.mark.django_db
class TestAgentThroughTheChat:

    @pytest.fixture
    def chat(self, context):
        provider = LLMProvider.objects.create(name="agent", provider_type="openai", model_name="m", api_key="k", max_context_tokens=128000)
        with patch("ai_core.models.AITaskConfig._auto_populate_if_first_provider", create=True):
            AITaskConfig.objects.get_or_create(task_type="chat", provider=provider, defaults={"is_default_for_chat": True})
        chat = Chat.objects.get(id=context.chat_id)
        chat.provider_id = provider.id
        chat.save()
        return chat

    def test_the_answer_streams_steps_and_cites_the_page(self, chat):
        model = ScriptedModel(read_page_6(), [("text", "ReFinED takes 20 s [1].")], [("text", "1. It's 15 s.")],
                              [("text", "ReFinED takes 15 s [1].")])
        client = __import__("rest_framework.test", fromlist=["APIClient"]).APIClient()
        client.force_authenticate(chat.user)

        with patch("ai_core.services.chat_service.LongTermMemoryService") as memory, \
             patch("ai_core.services.llm_service.ProviderFactory.get_provider", return_value=model), \
             patch("chats.tasks.generate_chat_title.delay"):
            memory.return_value.build_memory_context.return_value = ""
            response = client.post(f"/api/chats/{chat.uuid}/messages/", {"content": "How fast is ReFinED?"})
            assert response.status_code == 200, response.data
            events = [json.loads(line) for line in b"".join(response.streaming_content).decode().splitlines()]

        steps = [e for e in events if e["type"] == "step"]
        assert [s["status"] for s in steps] == ["running", "done", "running", "done"]
        assert all("output" not in s for s in steps)  # tool outputs stay on the server
        answer = Message.objects.get(chat=chat, role=Message.Role.ASSISTANT)
        assert answer.content == "ReFinED takes 15 s [1].\n\n**References:**\n[1] refined.pdf, p. 6\n"
        assert answer.trace == [{"tool": "read_document", "arguments": {"name": "refined.pdf", "part": "6"}, "summary": "Read refined.pdf, p. 6"},
                                {"tool": "check_answer", "arguments": {}, "summary": "Checked the answer"}]
        # The agent was told which documents it can read.
        assert "refined.pdf (7 pages, done)" in model.calls[0]["messages"][0]["content"]

    def test_providers_without_tools_keep_the_single_pass_pipeline(self, chat):
        with patch("ai_core.services.chat_service.LLMService") as llm, \
             patch("ai_core.services.chat_service.LongTermMemoryService"), \
             patch("ai_core.services.chat_service.WebKnowledgeService"), \
             patch("ai_core.services.chat_service.DocumentRAGService") as rag:
            llm.return_value.provider.supports_tools = False
            llm.return_value.provider_config.max_context_tokens = 128000
            llm.return_value.stream.return_value = iter(["Plain answer."])
            rag.return_value.build_knowledge_context.return_value = ("", [])
            service = ChatGenerationService(chat.user_id, chat.id, is_temporary=True)
            events = list(service.answer_events(service.prepare("q")))

        assert events == [{"type": "text", "text": "Plain answer."}]


@pytest.mark.django_db
def test_the_first_turn_can_be_made_to_search_the_documents(context):
    model = ScriptedModel(read_page_6(), [("text", "Answer.")])
    agent = ResearchAgent(model, context, tool_definitions(web=True), max_steps=8, token_budget=100_000, first_tool="search_documents")

    run(agent, [{"role": "user", "content": "q"}])

    assert [c["tool_choice"] for c in model.calls] == ["search_documents", "auto"]


def test_openai_gets_a_forced_tool_in_its_own_format():
    from types import SimpleNamespace
    from ai_core.llm_providers.openai_provider import OpenAIProvider

    with patch("ai_core.llm_providers.openai_provider.OpenAI") as client_cls:
        create = client_cls.return_value.chat.completions.create
        create.return_value = iter([])
        config = SimpleNamespace(api_key="k", model_name="m", base_url=None, max_context_tokens=1000)
        list(OpenAIProvider(config).stream_turn([{"role": "user", "content": "q"}], [], tool_choice="search_documents"))

    assert create.call_args.kwargs["tool_choice"] == {"type": "function", "function": {"name": "search_documents"}}


@pytest.mark.django_db
def test_a_long_answer_streams_as_it_is_written(context):
    chunks = [("text", "word " * 50), ("text", "more "), ("text", "end.")]
    agent = ResearchAgent(ScriptedModel(chunks), context, tool_definitions(web=False), max_steps=8, token_budget=100_000)

    events = run(agent, [{"role": "user", "content": "q"}])

    # Held back until it's clearly not a preamble, then streamed piece by piece.
    assert [e["text"] for e in events] == ["word " * 50, "more ", "end."]
    assert agent.answer == "word " * 50 + "more end."


@pytest.mark.django_db
def test_a_short_answer_is_sent_when_the_turn_ends(context):
    agent = ResearchAgent(ScriptedModel([("text", "Yes."), ("text", " 3.")]), context, tool_definitions(web=False), max_steps=8, token_budget=100_000)

    assert run(agent, [{"role": "user", "content": "q"}]) == [{"type": "text", "text": "Yes. 3."}]


class StallingModel(ScriptedModel):
    """Stalls in the middle of its first answer, then answers in full."""

    def stream_turn(self, messages, tools, tool_choice="auto", reasoning_effort=None):
        from ai_core.exceptions import ProviderStalled
        self.calls.append({"tool_choice": tool_choice})
        if len(self.calls) == 1:
            yield "text", "ReFinED takes 15 s on "
            raise ProviderStalled("The read operation timed out")
        yield "text", "ReFinED takes 15 s [1]."


@pytest.mark.django_db
def test_a_stalled_answer_is_retried_and_the_partial_text_dropped(context):
    agent = ResearchAgent(StallingModel(), context, tool_definitions(web=False), max_steps=0, token_budget=100_000)

    events = run(agent, [{"role": "user", "content": "q"}])

    assert events == [{"type": "text", "text": "ReFinED takes 15 s on "}, {"type": "reset"},
                      {"type": "text", "text": "ReFinED takes 15 s [1]."}]
    assert agent.answer == "ReFinED takes 15 s [1]."


def test_openai_reports_a_stream_that_stops_mid_answer_as_stalled():
    import httpx
    from types import SimpleNamespace
    from ai_core.exceptions import ProviderStalled
    from ai_core.llm_providers.openai_provider import OpenAIProvider

    def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Partial", tool_calls=None))])
        raise httpx.ReadTimeout("The read operation timed out")

    with patch("ai_core.llm_providers.openai_provider.OpenAI") as client_cls:
        client_cls.return_value.chat.completions.create.return_value = chunks()
        config = SimpleNamespace(api_key="k", model_name="m", base_url=None, max_context_tokens=1000)
        with pytest.raises(ProviderStalled):
            list(OpenAIProvider(config).stream_turn([{"role": "user", "content": "q"}], []))


@pytest.mark.django_db
class TestAnswerReview:

    def agent(self, context, model):
        return ResearchAgent(model, context, tool_definitions(web=False), max_steps=8, token_budget=100_000, review=True)

    def test_the_draft_is_critiqued_and_only_the_final_answer_is_sent(self, context):
        model = ScriptedModel(read_page_6(), [("text", "ReFinED takes about 20 s [1].")],
                              [("text", "1. The time is 15 s on p. 6, not 20 s.")], [("text", "ReFinED takes 15 s [1].")])
        messages = [{"role": "user", "content": "How fast is ReFinED?"}]

        events = run(self.agent(context, model), messages)

        assert [(e["type"], e.get("tool"), e.get("status")) for e in events] == [
            ("step", "read_document", "running"), ("step", "read_document", "done"),
            ("step", "check_answer", "running"), ("step", "check_answer", "done"),
            ("text", None, None),
        ]
        assert events[-1]["text"] == "ReFinED takes 15 s [1]."
        # The model saw its draft, was asked for a critique, then wrote the answer from it.
        roles = [(m["role"], m["content"][:40]) for m in messages[-4:]]
        assert roles[0] == ("assistant", "ReFinED takes about 20 s [1].")
        assert roles[1][0] == "user" and "list of its problems" in messages[-4 + 1]["content"]
        assert roles[2] == ("assistant", "1. The time is 15 s on p. 6, not 20 s.")
        assert roles[3][0] == "user" and "write the final answer" in messages[-1]["content"]
        assert [c["tool_choice"] for c in model.calls] == ["auto", "auto", "auto", "none"]

    def test_the_critique_can_use_tools_before_the_answer(self, context):
        model = ScriptedModel(read_page_6(), [("text", "Draft.")], read_page_6(), [("text", "Problems: none.")],
                              [("text", "Checked answer.")])

        events = run(self.agent(context, model), [{"role": "user", "content": "q"}])

        tools = [(e["tool"], e["status"]) for e in events if e["type"] == "step"]
        assert tools[2:] == [("check_answer", "running"), ("check_answer", "done"), ("read_document", "running"), ("read_document", "done")]
        assert events[-1] == {"type": "text", "text": "Checked answer."}

    def test_answers_without_tools_are_not_checked(self, context):
        model = ScriptedModel([("text", "Hello!")])

        assert run(self.agent(context, model), [{"role": "user", "content": "hi"}]) == [{"type": "text", "text": "Hello!"}]

    def test_an_empty_final_turn_keeps_the_draft(self, context):
        model = ScriptedModel(read_page_6(), [("text", "ReFinED takes 15 s [1].")], [("text", "No problems.")], [])

        agent = self.agent(context, model)
        events = run(agent, [{"role": "user", "content": "q"}])

        assert events[-1] == {"type": "text", "text": "ReFinED takes 15 s [1]."}
        assert agent.answer == "ReFinED takes 15 s [1]."

    def test_out_of_steps_during_the_critique_still_ends_with_an_answer(self, context):
        model = ScriptedModel(read_page_6(), [("text", "Draft [1].")], [("text", "Fine.")], [("text", "Final [1].")])
        agent = ResearchAgent(model, context, tool_definitions(web=False), max_steps=2, token_budget=100_000, review=True)

        events = run(agent, [{"role": "user", "content": "q"}])

        assert [c["tool_choice"] for c in model.calls] == ["auto", "auto", "none", "none"]
        assert events[-1] == {"type": "text", "text": "Final [1]."}


@pytest.mark.django_db
def test_the_agent_asks_for_the_configured_reasoning_effort(context):
    model = ScriptedModel(read_page_6(), [("text", "Answer.")])

    run(ResearchAgent(model, context, tool_definitions(web=False), max_steps=8, token_budget=100_000, reasoning_effort="high"),
        [{"role": "user", "content": "q"}])

    assert [c["reasoning_effort"] for c in model.calls] == ["high", "high"]


def openai_provider():
    from types import SimpleNamespace
    from ai_core.llm_providers.openai_provider import OpenAIProvider
    return OpenAIProvider(SimpleNamespace(api_key="k", model_name="m", base_url=None, max_context_tokens=1000))


def test_openai_sends_the_reasoning_effort_only_when_asked():
    with patch("ai_core.llm_providers.openai_provider.OpenAI") as client_cls:
        create = client_cls.return_value.chat.completions.create
        create.return_value = iter([])
        provider = openai_provider()
        list(provider.stream_turn([{"role": "user", "content": "q"}], [], reasoning_effort="high"))
        list(provider.stream_turn([{"role": "user", "content": "q"}], []))

    assert create.call_args_list[0].kwargs["reasoning_effort"] == "high"
    assert "reasoning_effort" not in create.call_args_list[1].kwargs


def test_a_model_that_rejects_reasoning_effort_is_asked_again_without_it():
    import httpx
    from openai import BadRequestError

    rejected = BadRequestError("Unsupported parameter: 'reasoning_effort'", response=httpx.Response(400, request=httpx.Request("POST", "http://x")), body=None)
    with patch("ai_core.llm_providers.openai_provider.OpenAI") as client_cls:
        create = client_cls.return_value.chat.completions.create
        create.side_effect = [rejected, iter([]), iter([])]
        provider = openai_provider()
        list(provider.stream_turn([{"role": "user", "content": "q"}], [], reasoning_effort="high"))
        list(provider.stream_turn([{"role": "user", "content": "q"}], [], reasoning_effort="high"))

    assert [("reasoning_effort" in c.kwargs) for c in create.call_args_list] == [True, False, False]
