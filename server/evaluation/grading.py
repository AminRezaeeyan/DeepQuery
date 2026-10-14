"""Grades an agent answer: number checks, citations, retrieval, and a judge model."""
import json
import re

# Persian and Arabic-Indic digits, and the Persian decimal/thousands separators.
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
REF_MARKER = "**References:**"


def normalise_numbers(text: str) -> str:
    text = text.translate(DIGITS).replace("٫", ".")
    # Drop thousands separators: "1,393" and "۱٬۳۹۳" become "1393".
    return re.sub(r"(?<=\d)[,٬](?=\d{3}(?!\d))", "", text)


def extract_numbers(text: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", normalise_numbers(text))]


def check_numbers(answer: str, expected: list[dict]) -> list[dict]:
    """For each expected {value, tol}, whether some number in the answer is within tol."""
    found = extract_numbers(answer)
    results = []
    for spec in expected:
        value, tol = float(spec["value"]), float(spec.get("tol", 0))
        closest = min(found, key=lambda n: abs(n - value), default=None)
        results.append({
            "value": value,
            "tol": tol,
            "found": closest is not None and abs(closest - value) <= tol + 1e-9,
            "closest": closest,
        })
    return results


def split_answer(text: str) -> tuple[str, dict[int, str]]:
    """Separates the answer body from the reference list the server appends."""
    at = text.rfind(REF_MARKER)
    if at == -1:
        return text, {}
    references = {}
    for line in text[at + len(REF_MARKER):].splitlines():
        m = re.match(r"^\s*\[(\d+)\]\s+(.+?)\s*$", line)
        if m:
            references[int(m.group(1))] = m.group(2)
    return text[:at].rstrip(), references


def source_of(label: str) -> str:
    """The source behind a reference label: "refined.pdf, p. 6" -> "refined.pdf"."""
    return re.sub(r", (p\. \d+|sheet: .+)$", "", label)


def check_citations(body: str, references: dict[int, str], expected_files: list[str]) -> dict:
    cited = sorted({int(n) for n in re.findall(r"\[(\d{1,3})\]", body)})
    cited_files = sorted({source_of(references[n]) for n in cited if n in references})
    return {
        "cited_ids": cited,
        "invalid_ids": [n for n in cited if n not in references],
        "cited_files": cited_files,
        "expected_files": expected_files,
        "expected_cited": all(f in cited_files for f in expected_files),
    }


def check_retrieval(retrieved_files: list[str], expected_files: list[str]) -> dict:
    return {
        "retrieved_files": retrieved_files,
        "expected_files": expected_files,
        "hit": all(f in retrieved_files for f in expected_files),
    }


# Enough for the judge to check claims against what the agent actually saw.
JUDGE_CONTEXT_CHARS = 60000
JUDGE_ATTEMPTS = 2

JUDGE_SYSTEM = """You grade answers from a research assistant against a reference answer.
Be strict and literal. A key point is met only if the answer states it correctly; numbers
must match the reference (rounding to the shown precision is fine). Extra correct detail is
fine. Wrong or unsupported claims count against the answer even if the key points are met.
Reply with JSON only, no prose and no code fences."""

JUDGE_FORMAT = """{
  "key_points": [{"point": "<key point>", "met": true, "note": "<short reason>"}],
  "unsupported_claims": ["<claims in the answer that are wrong or not supported by the sources>"],
  "correct": true,
  "reasoning": "<two or three sentences>"
}"""


def judge_messages(question, answer_body: str, references: dict, retrieved_context: str) -> list[dict]:
    expectation = (
        "The sources do NOT contain the answer. The answer is correct only if it says so clearly "
        "and does not invent a value."
        if question.abstain
        else "The answer is correct only if every key point is met and nothing it claims is wrong."
    )
    language = "The answer should be written in Persian." if question.language == "fa" else ""
    payload = {
        "question": question.question.strip(),
        "reference_answer": question.answer.strip(),
        "key_points": question.grading.get("key_points", []),
        "expectation": f"{expectation} {language}".strip(),
        "answer_to_grade": answer_body,
        "answer_references": references,
        "retrieved_sources_excerpt": retrieved_context[:JUDGE_CONTEXT_CHARS],
    }
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"Grade this answer.\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\nReply in this JSON format:\n{JUDGE_FORMAT}"},
    ]


def parse_judge_reply(text: str) -> dict:
    """Reads the judge's JSON, tolerating code fences or text around it."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("The judge reply contains no JSON object.")
    data = json.loads(cleaned[start:end + 1])
    points = data.get("key_points") or []
    met = sum(1 for p in points if p.get("met") is True)
    data["key_points_met"] = met
    data["key_points_total"] = len(points)
    data["score"] = round(met / len(points), 3) if points else (1.0 if data.get("correct") else 0.0)
    data["correct"] = bool(data.get("correct"))
    return data


def judge(provider, question, answer_body: str, references: dict, retrieved_context: str) -> dict:
    """Asks the judge model to grade the answer. Returns the parsed verdict and the raw reply."""
    messages = judge_messages(question, answer_body, references, retrieved_context)
    for attempt in range(1, JUDGE_ATTEMPTS + 1):
        try:
            raw = "".join(provider.stream(messages))
            break
        except Exception:
            if attempt == JUDGE_ATTEMPTS:
                raise  # the runner records the error and marks the answer ungraded
    try:
        verdict = parse_judge_reply(raw)
        error = None
    except (ValueError, json.JSONDecodeError) as e:
        verdict, error = None, f"Unreadable judge reply: {e}"
    return {"verdict": verdict, "raw_reply": raw, "error": error, "prompt": messages}
