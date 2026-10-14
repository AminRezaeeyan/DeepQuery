from types import SimpleNamespace

from evaluation import grading


def test_numbers_in_persian_digits_and_with_separators_are_found():
    answer = "حدود ۸۴٫۶٪ و ۱٬۳۹۳ سند؛ English: 1,393 docs and 925,926 mentions, ratio 61.1x"

    results = grading.check_numbers(answer, [{"value": 84.6, "tol": 0.1}, {"value": 1393}, {"value": 925926, "tol": 2000}, {"value": 61.1}])

    assert [r["found"] for r in results] == [True, True, True, True]


def test_lists_of_numbers_are_not_merged():
    assert grading.extract_numbers("88.6, 89.1 and 74.0") == [88.6, 89.1, 74.0]


def test_missing_numbers_report_the_closest_value():
    [result] = grading.check_numbers("about 60 times faster", [{"value": 61.1, "tol": 0.1}])

    assert result["found"] is False
    assert result["closest"] == 60


def test_answers_split_into_body_and_references():
    body, refs = grading.split_answer("ReFinED is faster [1][2].\n\n**References:**\n[1] refined.pdf\n[2] https://example.org/x\n")

    assert body == "ReFinED is faster [1][2]."
    assert refs == {1: "refined.pdf", 2: "https://example.org/x"}


def test_citation_check_flags_missing_ids_and_expected_files():
    result = grading.check_citations("A [1] and B [3].", {1: "refined.pdf", 2: "blink.pdf"}, ["refined.pdf", "blink.pdf"])

    assert result["invalid_ids"] == [3]
    assert result["cited_files"] == ["refined.pdf"]
    assert result["expected_cited"] is False


def test_judge_reply_is_parsed_even_with_code_fences():
    verdict = grading.parse_judge_reply(
        'Here you go:\n```json\n{"key_points": [{"point": "a", "met": true}, {"point": "b", "met": false}], "correct": false, "reasoning": "r"}\n```'
    )

    assert verdict["key_points_met"] == 1
    assert verdict["score"] == 0.5
    assert verdict["correct"] is False


def test_judge_sends_the_question_and_reference_to_the_model():
    sent = []

    class FakeJudge:
        def stream(self, messages):
            sent.append(messages)
            yield '{"key_points": [{"point": "p", "met": true}], "correct": true, "reasoning": "ok"}'

    question = SimpleNamespace(question="How fast?", answer="61x", grading={"key_points": ["61x faster"]}, abstain=False, language="fa")

    result = grading.judge(FakeJudge(), question, "حدود ۶۱ برابر", {}, "Table 5 ...")

    assert result["verdict"]["correct"] is True
    prompt = sent[0][1]["content"]
    assert "61x faster" in prompt and "حدود ۶۱ برابر" in prompt and "Persian" in prompt
