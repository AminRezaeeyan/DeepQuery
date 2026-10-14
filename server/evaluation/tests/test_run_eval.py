import json
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command

from ai_core.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from ai_core.models import EmbeddingProvider, LLMProvider
from chats.models import Chat
from documents.models import Document

QUESTIONS = """
- id: t1
  category: paper_fact
  language: en
  question: How fast is ReFinED?
  answer: 61 times faster.
  sources: [notes.md]
  cite: [notes.md]
  requires: [retrieval]
  grading:
    numbers: [{value: 61, tol: 0.5}]
    key_points: [About 61x faster]
"""


@pytest.fixture
def setup(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "notes.md").write_text("ReFinED is 61 times faster than the BLINK cross-encoder.")
    (tmp_path / "questions.yaml").write_text(QUESTIONS)
    EmbeddingProvider.objects.create(name="emb", provider_type="openai", api_key="k", model_name="m", dimension=3, max_tokens=512)
    agent = LLMProvider.objects.create(name="agent", provider_type="openai", model_name="m", api_key="k")
    return tmp_path, agent


class FakeJudge:
    def stream(self, messages):
        yield '{"key_points": [{"point": "About 61x faster", "met": true, "note": "ok"}], "correct": true, "reasoning": "matches"}'


def fake_stream(prepared, image_bytes=None, mime_type=None):
    yield {"type": "text", "text": "ReFinED is about 61 times faster [1].\n\n**References:**\n[1] notes.md\n"}


@pytest.mark.django_db
def test_run_eval_saves_every_answer_and_grade(setup):
    tmp_path, agent = setup
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5), \
         patch("evaluation.runner.ChatGenerationService") as service_cls, \
         patch("evaluation.runner.provider_instance", return_value=FakeJudge()):
        service_cls.return_value.prepare.return_value = {
            "agent": False,
            "messages": [{"role": "system", "content": "RULES"}, {"role": "user", "content": "<sources>\nnotes text\n</sources>\n\nHow fast?"}],
            "citation_map": {(1, ""): {"cite_id": 1, "url": None, "filename": "notes.md", "location": "", "label": "notes.md"}},
        }
        service_cls.return_value.answer_events.side_effect = fake_stream

        call_command(
            "run_eval",
            questions=str(tmp_path / "questions.yaml"),
            sources=str(tmp_path / "sources"),
            out=str(tmp_path / "runs"),
            provider=str(agent.id),
        )

    [run_dir] = list((tmp_path / "runs").iterdir())
    record = json.loads((run_dir / "questions" / "t1.json").read_text())
    assert record["agent"]["answer"].startswith("ReFinED is about 61 times faster [1].")
    assert record["agent"]["prompt_messages"][1]["content"].startswith("<sources>")
    assert record["documents"][0]["status"] == "done" and record["documents"][0]["chunks"] >= 1
    assert record["grading"]["correct"] is True
    assert record["grading"]["numbers_ok"] and record["grading"]["citations"]["expected_cited"] and record["grading"]["retrieval"]["hit"]

    summary = json.loads((run_dir / "run.json").read_text())["summary"]
    assert summary["accuracy"] == 1.0
    assert "61 times faster" in (run_dir / "answers" / "t1.md").read_text()
    assert "t1" in (run_dir / "report.md").read_text()

    # The eval chat, its documents and their files are cleaned up.
    assert not Chat.all_objects.filter(title="eval t1").exists()
    assert not Document.objects.exists()


class FailingJudge:
    def __init__(self, fail_probe=False):
        self.fail_probe = fail_probe
        self.calls = 0

    def stream(self, messages):
        self.calls += 1
        if self.fail_probe or self.calls > 2:  # the first two calls are the agent and judge probes
            raise RuntimeError("Error code: 404 - model_not_found")
        yield "OK"


def run(tmp_path, agent, judge):
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5), \
         patch("evaluation.runner.ChatGenerationService") as service_cls, \
         patch("evaluation.runner.provider_instance", return_value=judge):
        service_cls.return_value.prepare.return_value = {"agent": False, "messages": [], "citation_map": {}}
        service_cls.return_value.answer_events.side_effect = fake_stream
        call_command(
            "run_eval",
            questions=str(tmp_path / "questions.yaml"),
            sources=str(tmp_path / "sources"),
            out=str(tmp_path / "runs"),
            provider=str(agent.id),
        )


@pytest.mark.django_db
def test_a_failed_judge_call_leaves_the_answer_ungraded(setup):
    tmp_path, agent = setup

    run(tmp_path, agent, FailingJudge())

    [run_dir] = list((tmp_path / "runs").iterdir())
    grading = json.loads((run_dir / "questions" / "t1.json").read_text())["grading"]
    assert grading["ungraded"] is True
    assert grading["correct"] is False  # the number checks alone don't count as a pass
    assert json.loads((run_dir / "run.json").read_text())["summary"]["ungraded"] == ["t1"]
    assert "not graded" in (run_dir / "report.md").read_text()


@pytest.mark.django_db
def test_an_unreachable_model_stops_the_run_before_any_question(setup):
    from django.core.management.base import CommandError

    tmp_path, agent = setup

    with pytest.raises(CommandError, match="didn't answer"):
        run(tmp_path, agent, FailingJudge(fail_probe=True))

    assert not (tmp_path / "runs").exists()


TWO_QUESTIONS = QUESTIONS + QUESTIONS.replace("id: t1", "id: t2")


def run_with(tmp_path, agent, answer, **options):
    def stream(prepared, image_bytes=None, mime_type=None):
        yield {"type": "text", "text": answer}

    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5), \
         patch("evaluation.runner.ChatGenerationService") as service_cls, \
         patch("evaluation.runner.provider_instance", return_value=FakeJudge()):  # answers the model probe
        service_cls.return_value.prepare.return_value = {"agent": False, "messages": [], "citation_map": {}}
        service_cls.return_value.answer_events.side_effect = stream
        call_command("run_eval", questions=str(tmp_path / "questions.yaml"), sources=str(tmp_path / "sources"),
                     out=str(tmp_path / "runs"), provider=str(agent.id), no_judge=True, **options)


@pytest.mark.django_db
class TestRerun:

    def test_rerunning_a_question_replaces_only_its_result(self, setup):
        tmp_path, agent = setup
        (tmp_path / "questions.yaml").write_text(TWO_QUESTIONS)
        run_with(tmp_path, agent, "No idea.")
        [run_dir] = list((tmp_path / "runs").iterdir())
        first_t1 = (run_dir / "questions" / "t1.json").read_text()

        run_with(tmp_path, agent, "About 61 times faster.", rerun=str(run_dir), only="t2")

        assert list((tmp_path / "runs").iterdir()) == [run_dir]  # no new run
        assert (run_dir / "questions" / "t1.json").read_text() == first_t1
        t2 = json.loads((run_dir / "questions" / "t2.json").read_text())
        assert t2["agent"]["answer"] == "About 61 times faster." and t2["rerun"]
        run = json.loads((run_dir / "run.json").read_text())
        assert run["summary"]["questions"] == 2 and run["summary"]["correct"] == 1
        assert run["meta"]["reruns"][0]["questions"] == ["t2"]
        report_md = (run_dir / "report.md").read_text()
        assert "- Re-run on " in report_md and ": t2" in report_md
        assert "[t2](answers/t2.md) (re-run)" in report_md

    def test_a_rerun_must_use_the_same_models(self, setup):
        tmp_path, agent = setup
        run_with(tmp_path, agent, "No idea.")
        [run_dir] = list((tmp_path / "runs").iterdir())
        other = LLMProvider.objects.create(name="other", provider_type="openai", model_name="m2", api_key="k")

        with pytest.raises(CommandError, match="same --provider"):
            run_with(tmp_path, other, "61", rerun=str(run_dir), only="t1")

    def test_a_rerun_needs_the_questions_to_run(self, setup):
        tmp_path, agent = setup

        with pytest.raises(CommandError, match="--rerun needs --only"):
            run_with(tmp_path, agent, "61", rerun=str(tmp_path / "runs" / "x"))
