"""Loads and validates eval/questions.yaml."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ALLOWED_KEYS = {"id", "category", "language", "question", "sources", "image", "web_search", "answer", "grading", "cite", "requires"}


class QuestionFileError(ValueError):
    pass


@dataclass
class Question:
    id: str
    category: str
    language: str
    question: str
    answer: str
    grading: dict
    sources: list = field(default_factory=list)
    image: str | None = None
    web_search: bool = False
    cite: list = field(default_factory=list)
    requires: list = field(default_factory=list)

    @property
    def abstain(self) -> bool:
        return bool(self.grading.get("abstain"))


def load_questions(path: Path, sources_dir: Path, only: list[str] | None = None) -> list[Question]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise QuestionFileError("The questions file must be a list of questions.")

    questions, seen = [], set()
    for entry in raw:
        unknown = set(entry) - ALLOWED_KEYS
        if unknown:
            raise QuestionFileError(f"{entry.get('id')}: unknown keys {sorted(unknown)}")
        question = Question(**entry)
        if question.id in seen:
            raise QuestionFileError(f"Duplicate question id {question.id}")
        seen.add(question.id)

        grading = question.grading or {}
        if not (grading.get("numbers") or grading.get("key_points") or grading.get("abstain")):
            raise QuestionFileError(f"{question.id}: grading needs numbers, key_points or abstain")
        for name in [*question.sources, *question.cite, *([question.image] if question.image else [])]:
            if not (Path(sources_dir) / name).is_file():
                raise QuestionFileError(f"{question.id}: missing source file {name}")
        questions.append(question)

    if only:
        wanted = set(only)
        unknown = wanted - seen
        if unknown:
            raise QuestionFileError(f"Unknown question ids: {sorted(unknown)}")
        questions = [q for q in questions if q.id in wanted]
    return questions
