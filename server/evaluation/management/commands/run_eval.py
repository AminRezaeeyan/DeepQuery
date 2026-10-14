"""
Runs the evaluation set through the real chat pipeline and grades every answer.

    python manage.py run_eval                       # all questions
    python manage.py run_eval --only q01,q14        # a subset
    python manage.py run_eval --judge-provider 4    # pick the grading model (LLMProvider id or name)

Results go to eval/runs/<timestamp>-<commit>/ (see eval/README.md).
"""
import hashlib
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai_core.models import EmbeddingProvider, LLMProvider
from ai_core.services.provider_service import ProviderService
from evaluation import report
from evaluation.loader import QuestionFileError, load_questions
from evaluation.runner import ModelUnavailable, QuestionRunner

EVAL_DIR = Path(settings.BASE_DIR).parent / "eval"


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=EVAL_DIR.parent, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def find_provider(value):
    if value is None:
        return None
    query = LLMProvider.objects.filter(id=int(value)) if str(value).isdigit() else LLMProvider.objects.filter(name=value)
    provider = query.first()
    if not provider:
        raise CommandError(f"No LLM provider with id or name {value!r}.")
    return provider


class Command(BaseCommand):
    help = "Run the DeepQuery evaluation set and save every answer and grade."

    def add_arguments(self, parser):
        parser.add_argument("--questions", default=str(EVAL_DIR / "questions.yaml"))
        parser.add_argument("--sources", default=str(EVAL_DIR / "sources"))
        parser.add_argument("--out", default=str(EVAL_DIR / "runs"))
        parser.add_argument("--only", help="Comma-separated question ids, e.g. q01,q14")
        parser.add_argument("--provider", help="LLM provider (id or name) that answers. Default: the default chat provider.")
        parser.add_argument("--judge-provider", help="LLM provider (id or name) that grades. Default: same as --provider.")
        parser.add_argument("--no-judge", action="store_true", help="Grade with the deterministic checks only.")
        parser.add_argument("--keep-data", action="store_true", help="Keep the eval chats and indexed documents afterwards.")

    def handle(self, *args, **opts):
        try:
            questions = load_questions(opts["questions"], opts["sources"], only=opts["only"].split(",") if opts["only"] else None)
        except QuestionFileError as e:
            raise CommandError(str(e))

        agent = find_provider(opts["provider"]) or ProviderService.get_default_chat_provider()
        judge = None if opts["no_judge"] else (find_provider(opts["judge_provider"]) or agent)
        if judge and judge.id == agent.id:
            self.stdout.write(self.style.WARNING("The judge is the same model as the agent; a stronger judge gives fairer grades."))

        runner = QuestionRunner(Path(opts["sources"]), agent, judge, keep_data=opts["keep_data"])
        try:
            runner.check_models()
        except ModelUnavailable as e:
            raise CommandError(f"{e}\nFix the provider in the admin (model name, key or base URL) and run again.")

        commit = git("rev-parse", "--short", "HEAD") or "unknown"
        run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{commit}"
        run_dir = Path(opts["out"]) / run_id
        run_dir.mkdir(parents=True)
        embedding = EmbeddingProvider.objects.filter(is_active=True).first()
        meta = {
            "run_id": run_id,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "git_commit": commit,
            "git_dirty": bool(git("status", "--porcelain")),
            "questions_file_sha256": hashlib.sha256(Path(opts["questions"]).read_bytes()).hexdigest(),
            "agent_provider": f"{agent.name} ({agent.provider_type}: {agent.model_name})",
            "judge_provider": f"{judge.name} ({judge.provider_type}: {judge.model_name})" if judge else None,
            "embedding_provider": f"{embedding.name} ({embedding.model_name})" if embedding else None,
            "question_ids": [q.id for q in questions],
        }

        records, started = [], time.monotonic()
        for i, question in enumerate(questions, 1):
            self.stdout.write(f"[{i}/{len(questions)}] {question.id} ({question.category}) ...", ending="")
            self.stdout.flush()
            record = runner.run(question)
            report.write_question(run_dir, record)
            records.append(record)
            g = record["grading"]
            if g.get("ungraded"):
                status = self.style.WARNING("not graded (judge failed)")
            else:
                status = self.style.SUCCESS("correct") if g["correct"] else self.style.ERROR("incorrect")
            self.stdout.write(f" {status} (score {g['score']}, {record['timings'].get('answer_s')} s)")

        meta["duration_s"] = round(time.monotonic() - started, 1)
        meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
        summary = report.summarise(records)
        previous = report.latest_previous_run(Path(opts["out"]), run_dir)
        (run_dir / "run.json").write_text(json.dumps({"meta": meta, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
        report.write_report(run_dir, meta, summary, records, previous)

        self.stdout.write(self.style.SUCCESS(
            f"\nAccuracy {summary['correct']}/{summary['questions']} ({(summary['accuracy'] or 0) * 100:.1f}%). Results: {run_dir}"
        ))
