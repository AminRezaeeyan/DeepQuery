"""Runs one evaluation question end to end through the real chat pipeline."""
import logging
import mimetypes
import re
import time
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files import File

from ai_core.llm_providers.base import PROVIDER_REGISTRY
from ai_core.llm_providers.factory import ProviderFactory
from ai_core.models import EmbeddingChunk
from ai_core.services.chat_service import ChatGenerationService
from chats.models import Chat
from chats.services.chat_service import STREAM_ERROR_MARKER
from documents.models import Document
from documents.tasks import extract_and_index_document

from . import grading

logger = logging.getLogger(__name__)

EVAL_USER_EMAIL = "eval-runner@deepquery.local"


def eval_user():
    user, created = get_user_model().objects.get_or_create(email=EVAL_USER_EMAIL)
    if created:
        user.set_unusable_password()
        user.save()
    return user


def provider_instance(llm_provider):
    """An LLM provider object for any configured provider, whatever its tasks."""
    ProviderFactory._auto_import_providers()
    return PROVIDER_REGISTRY[llm_provider.provider_type](llm_provider)


def sources_block(messages: list[dict]) -> str:
    """The retrieved text the model saw, from the <sources> tag in the final user turn."""
    last = messages[-1]["content"] if messages else ""
    m = re.search(r"<sources>\n?(.*?)\n?</sources>", last, flags=re.DOTALL)
    return m.group(1) if m else ""


class QuestionRunner:
    def __init__(self, sources_dir: Path, agent_provider, judge_provider, keep_data: bool = False):
        self.sources_dir = Path(sources_dir)
        self.agent_provider = agent_provider
        self.judge = provider_instance(judge_provider) if judge_provider else None
        self.keep_data = keep_data
        self.user = eval_user()

    def run(self, question) -> dict:
        record = {"question": vars(question).copy(), "documents": [], "timings": {}}
        # A temporary chat never reads or writes long-term memory, so questions stay independent.
        chat = Chat.objects.create(user=self.user, provider_id=self.agent_provider.id, title=f"eval {question.id}", is_temporary=True)
        try:
            self._index_sources(chat, question, record)
            self._ask(chat, question, record)
            self._grade(question, record)
        finally:
            if not self.keep_data:
                chat.delete()  # documents, embeddings and files go with it
        return record

    def _index_sources(self, chat, question, record):
        started = time.monotonic()
        for name in question.sources:
            with open(self.sources_dir / name, "rb") as f:
                doc = Document.objects.create(chat=chat, user=self.user, original_filename=name, file=File(f, name=name))
            message = extract_and_index_document(doc.id)
            doc.refresh_from_db()
            chunks = EmbeddingChunk.objects.filter(
                embedded_object__content_type=ContentType.objects.get_for_model(Document),
                embedded_object__object_id=str(doc.pk),
            ).count()
            record["documents"].append({
                "file": name,
                "status": doc.status,
                "indexing_message": message,
                "extracted_chars": len(doc.extracted_text or ""),
                "extracted_preview": (doc.extracted_text or "")[:1500],
                "chunks": chunks,
            })
        record["timings"]["indexing_s"] = round(time.monotonic() - started, 2)

    def _ask(self, chat, question, record):
        image_bytes = mime_type = None
        if question.image:
            image_bytes = (self.sources_dir / question.image).read_bytes()
            mime_type = mimetypes.guess_type(question.image)[0]

        answer, error, prepared = "", None, None
        started = time.monotonic()
        first_token_at = None
        try:
            service = ChatGenerationService(
                self.user.id, chat.id, self.agent_provider.id, is_temporary=True, enable_web_search=question.web_search,
            )
            prepared = service.prepare(question.question.strip())
            record["timings"]["prepare_s"] = round(time.monotonic() - started, 2)
            for token in service.stream_prepared(prepared, image_bytes=image_bytes, mime_type=mime_type):
                if first_token_at is None:
                    first_token_at = time.monotonic()
                answer += token
        except Exception as e:  # recorded in the results; the run continues with the next question
            logger.exception("Question %s failed", question.id)
            error = f"{type(e).__name__}: {e}"

        if STREAM_ERROR_MARKER in answer:
            answer, _, tail = answer.partition(STREAM_ERROR_MARKER)
            error = error or tail
        finished = time.monotonic()
        record["timings"]["first_token_s"] = round(first_token_at - started, 2) if first_token_at else None
        record["timings"]["answer_s"] = round(finished - started, 2)

        web_documents = list(Document.objects.filter(chat=chat, source_type=Document.SourceTypeChoices.WEB).values_list("source_url", flat=True))
        citation_map = (prepared or {}).get("citation_map", {})
        record["agent"] = {
            "answer": answer,
            "error": error,
            "prompt_messages": (prepared or {}).get("messages", []),
            "retrieved_sources": [c["url"] or c["filename"] for c in sorted(citation_map.values(), key=lambda c: c["cite_id"])],
            "web_pages_fetched": web_documents,
        }

    def _grade(self, question, record):
        agent = record["agent"]
        body, references = grading.split_answer(agent["answer"])
        result = {
            "numbers": grading.check_numbers(body, question.grading.get("numbers", [])),
            "citations": grading.check_citations(body, references, question.cite),
            "retrieval": grading.check_retrieval(agent["retrieved_sources"], question.cite),
        }
        result["numbers_ok"] = all(n["found"] for n in result["numbers"])

        if self.judge and agent["answer"].strip():
            try:
                result["judge"] = grading.judge(self.judge, question, body, references, grading_context(agent))
            except Exception as e:  # a failed judge call shouldn't stop the run
                logger.exception("Judge failed on %s", question.id)
                result["judge"] = {"verdict": None, "raw_reply": "", "error": f"{type(e).__name__}: {e}"}
        else:
            result["judge"] = {"verdict": None, "raw_reply": "", "error": "no answer" if self.judge else "judge disabled"}

        verdict = result["judge"].get("verdict")
        if verdict:
            result["correct"], result["score"] = verdict["correct"], verdict["score"]
        else:
            # Without a judge, fall back to the deterministic checks where there are any.
            has_numbers = bool(result["numbers"])
            result["correct"] = bool(agent["answer"].strip()) and has_numbers and result["numbers_ok"]
            result["score"] = (sum(n["found"] for n in result["numbers"]) / len(result["numbers"])) if has_numbers else 0.0
            result["graded_without_judge"] = True
        record["grading"] = result


def grading_context(agent: dict) -> str:
    return sources_block(agent["prompt_messages"])
