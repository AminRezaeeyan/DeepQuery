from pathlib import Path

import pytest

from evaluation.loader import QuestionFileError, load_questions

EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"


def test_the_real_question_set_is_valid():
    questions = load_questions(EVAL_DIR / "questions.yaml", EVAL_DIR / "sources")

    assert len(questions) >= 30
    assert any(q.language == "fa" for q in questions)
    assert any(q.abstain for q in questions)


def write(tmp_path, text):
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "a.md").write_text("hello")
    path = tmp_path / "q.yaml"
    path.write_text(text)
    return path, tmp_path / "sources"


QUESTION = """
- id: q1
  category: paper_fact
  language: en
  question: Q?
  answer: A.
  sources: [{source}]
  grading: {grading}
"""


@pytest.mark.parametrize(
    "source, grading, message",
    [
        ("missing.md", "{key_points: [x]}", "missing source file"),
        ("a.md", "{}", "grading needs"),
    ],
)
def test_invalid_questions_are_rejected(tmp_path, source, grading, message):
    path, sources = write(tmp_path, QUESTION.format(source=source, grading=grading))

    with pytest.raises(QuestionFileError, match=message):
        load_questions(path, sources)


def test_only_selects_questions_and_rejects_unknown_ids(tmp_path):
    path, sources = write(tmp_path, QUESTION.format(source="a.md", grading="{key_points: [x]}"))

    assert [q.id for q in load_questions(path, sources, only=["q1"])] == ["q1"]
    with pytest.raises(QuestionFileError, match="Unknown question ids"):
        load_questions(path, sources, only=["q9"])
