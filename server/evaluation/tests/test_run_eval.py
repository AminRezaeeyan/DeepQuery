import json
from unittest.mock import patch

import pytest
from django.core.management import call_command

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
    yield "ReFinED is about 61 times faster [1].\n\n**References:**\n[1] notes.md\n"


@pytest.mark.django_db
def test_run_eval_saves_every_answer_and_grade(setup):
    tmp_path, agent = setup
    with patch.object(OpenAIEmbeddingProvider, "embed_documents", side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]), \
         patch.object(OpenAIEmbeddingProvider, "embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch.object(OpenAIEmbeddingProvider, "count_tokens", return_value=5), \
         patch("evaluation.runner.ChatGenerationService") as service_cls, \
         patch("evaluation.runner.provider_instance", return_value=FakeJudge()):
        service_cls.return_value.prepare.return_value = {
            "messages": [{"role": "system", "content": "RULES"}, {"role": "user", "content": "<sources>\nnotes text\n</sources>\n\nHow fast?"}],
            "citation_map": {1: {"cite_id": 1, "url": None, "filename": "notes.md"}},
        }
        service_cls.return_value.stream_prepared.side_effect = fake_stream

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
