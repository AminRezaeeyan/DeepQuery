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


def test_judge_retries_once_after_a_failure():
    class FlakyJudge:
        calls = 0

        def stream(self, messages):
            FlakyJudge.calls += 1
            if FlakyJudge.calls == 1:
                raise TimeoutError("read timed out")
            yield '{"key_points": [], "correct": true, "reasoning": "ok"}'

    question = SimpleNamespace(question="q", answer="a", grading={}, abstain=False, language="en")

    result = grading.judge(FlakyJudge(), question, "answer", {}, "")

    assert FlakyJudge.calls == 2
    assert result["verdict"]["correct"] is True


def test_sources_are_read_from_messages_with_an_attached_image():
    from evaluation.runner import sources_block

    messages = [{"role": "user", "content": [{"type": "text", "text": "<sources>\nTable 5\n</sources>\n\nq"}, {"type": "image_url", "image_url": {"url": "data:..."}}]}]

    assert sources_block(messages) == "Table 5"


def test_the_judge_gets_a_longer_timeout():
    from unittest.mock import MagicMock, patch
    from ai_core.llm_providers.factory import ProviderFactory
    from evaluation.runner import provider_instance

    ProviderFactory._auto_import_providers()  # load the real registry first, then stub it
    instance = MagicMock()
    original_client = instance.client
    with patch.dict("ai_core.llm_providers.base.PROVIDER_REGISTRY", {"openai": lambda config: instance}):
        result = provider_instance(SimpleNamespace(provider_type="openai"), timeout=600)

    original_client.with_options.assert_called_once_with(timeout=600)
    assert result.client is original_client.with_options.return_value
