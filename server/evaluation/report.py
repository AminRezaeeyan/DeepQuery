"""Writes a run's results: full JSON per question, readable answers, a summary and a report."""
import json
from collections import defaultdict
from pathlib import Path


def summarise(records: list[dict]) -> dict:
    def rate(values):
        values = list(values)
        return round(sum(values) / len(values), 3) if values else None

    graded = [r["grading"] for r in records]
    by_category, by_capability = defaultdict(list), defaultdict(list)
    for r in records:
        by_category[r["question"]["category"]].append(r["grading"]["correct"])
        for capability in r["question"]["requires"]:
            by_capability[capability].append(r["grading"]["correct"])

    with_numbers = [g for g in graded if g["numbers"]]
    with_cites = [r for r in records if r["question"]["cite"]]
    abstain = [r for r in records if r["question"]["grading"].get("abstain")]
    timings = [r["timings"].get("answer_s") for r in records if r["timings"].get("answer_s") is not None]
    return {
        "questions": len(records),
        "correct": sum(g["correct"] for g in graded),
        "accuracy": rate(g["correct"] for g in graded),
        "mean_score": rate(g["score"] for g in graded),
        "numbers_found_rate": rate(g["numbers_ok"] for g in with_numbers),
        "retrieval_hit_rate": rate(r["grading"]["retrieval"]["hit"] for r in with_cites),
        "passage_hit_rate": rate(
            r["grading"]["retrieval"]["passages_hit"] for r in records if r["grading"]["retrieval"].get("passages_hit") is not None
        ),
        "expected_source_cited_rate": rate(r["grading"]["citations"]["expected_cited"] for r in with_cites),
        "invalid_citation_answers": sum(bool(g["citations"]["invalid_ids"]) for g in graded),
        "abstention_accuracy": rate(r["grading"]["correct"] for r in abstain),
        "errors": [r["question"]["id"] for r in records if r["agent"]["error"]],
        "judge_failures": [r["question"]["id"] for r in records if not r["grading"]["judge"].get("verdict")],
        "ungraded": [r["question"]["id"] for r in records if r["grading"].get("ungraded")],
        "mean_answer_seconds": rate(timings),
        "accuracy_by_category": {k: rate(v) for k, v in sorted(by_category.items())},
        "accuracy_by_capability": {k: rate(v) for k, v in sorted(by_capability.items())},
    }


def write_question(run_dir: Path, record: dict):
    qid = record["question"]["id"]
    (run_dir / "questions").mkdir(exist_ok=True)
    (run_dir / "answers").mkdir(exist_ok=True)
    (run_dir / "questions" / f"{qid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "answers" / f"{qid}.md").write_text(answer_markdown(record), encoding="utf-8")


def answer_markdown(record: dict) -> str:
    q, agent, g = record["question"], record["agent"], record["grading"]
    verdict = (g["judge"] or {}).get("verdict") or {}
    lines = [
        f"# {q['id']} · {q['category']} · {'not graded (judge failed)' if g.get('ungraded') else ('correct' if g['correct'] else 'incorrect')} (score {g['score']})",
        "",
        "## Question",
        "",
        q["question"].strip(),
        "",
        f"Sources: {', '.join(q['sources']) or 'none'}"
        + (f" · Image: {q['image']}" if q.get("image") else "")
        + (" · Web search on" if q.get("web_search") else ""),
        "",
        "## Agent answer",
        "",
        agent["answer"].strip() or "_(empty)_",
    ]
    if agent["error"]:
        lines += ["", f"**Error:** {agent['error']}"]
    lines += ["", "## Reference answer", "", q["answer"].strip(), "", "## Grading", ""]
    for point in verdict.get("key_points", []):
        lines.append(f"- {'✅' if point.get('met') else '❌'} {point.get('point')} — {point.get('note', '')}")
    for claim in verdict.get("unsupported_claims", []) or []:
        lines.append(f"- ⚠️ Unsupported: {claim}")
    if verdict.get("reasoning"):
        lines += ["", f"Judge: {verdict['reasoning']}"]
    if g["judge"].get("error"):
        lines += ["", f"Judge error: {g['judge']['error']}"]
    numbers = ", ".join(f"{n['value']:g} {'✅' if n['found'] else '❌'}" for n in g["numbers"])
    lines += [
        "",
        f"- Numbers: {numbers or '—'}",
        f"- Retrieved sources: {', '.join(agent.get('retrieved_passages') or agent['retrieved_sources']) or 'none'}",
        *[f"- Needed passage {'✅' if p['found'] else '❌'} ({p['source']}): {p['passage']}" for p in g["retrieval"].get("passages", [])],
        f"- Cited: {', '.join(g['citations']['cited_files']) or 'none'} (expected: {', '.join(q['cite']) or 'none'})",
        f"- Time: {record['timings']}",
        "",
    ]
    return "\n".join(lines)


def write_report(run_dir: Path, meta: dict, summary: dict, records: list[dict], previous: dict | None):
    def pct(v):
        return "—" if v is None else f"{v * 100:.1f}%"

    stopped = f" · Stopped early: {summary['questions']} of {len(meta['question_ids'])} answered" if meta.get("stopped_early") else ""
    lines = [
        f"# Evaluation run {meta['run_id']}",
        "",
        f"- Commit: `{meta['git_commit']}`{' (uncommitted changes)' if meta['git_dirty'] else ''}",
        f"- Agent model: {meta['agent_provider']} (reasoning effort: {meta.get('agent_reasoning_effort', 'default')})"
        f" · Judge model: {meta['judge_provider'] or 'none'} · Embeddings: {meta['embedding_provider']}",
        f"- Questions: {summary['questions']} · Duration: {meta['duration_s']} s{stopped}",
        *[
            f"- Re-run on {r['at'][:16].replace('T', ' ')} at commit `{r['git_commit']}`"
            f"{' (uncommitted changes)' if r['git_dirty'] else ''}"
            f", reasoning effort {r.get('agent_reasoning_effort', 'default')}"
            f"{' (stopped early)' if r.get('stopped_early') else ''}"
            f"{' (entry reconstructed from the saved answers)' if r.get('reconstructed') else ''}: {', '.join(r['questions'])}"
            for r in meta.get("reruns", [])
        ],
        "",
        "## Results",
        "",
        f"| Metric | Value |{' Previous |' if previous else ''}",
        f"|---|---|{'---|' if previous else ''}",
    ]
    rows = [
        ("Accuracy", "accuracy"),
        ("Mean key-point score", "mean_score"),
        ("Expected numbers found", "numbers_found_rate"),
        ("Retrieved the needed passages", "passage_hit_rate"),
        ("Retrieved the right source (file level)", "retrieval_hit_rate"),
        ("Cited the right source", "expected_source_cited_rate"),
        ("Declined unanswerable questions", "abstention_accuracy"),
    ]
    for label, key in rows:
        prev = f" {pct(previous['summary'].get(key))} |" if previous else ""
        lines.append(f"| {label} | {pct(summary[key])} |{prev}")
    lines += [
        "",
        f"Correct: {summary['correct']}/{summary['questions']} · Answers citing a missing source: {summary['invalid_citation_answers']}"
        f" · Errors: {', '.join(summary['errors']) or 'none'} · Not graded (judge failed): {', '.join(summary['ungraded']) or 'none'}",
        "",
        "## By category",
        "",
        "| Category | Accuracy |",
        "|---|---|",
        *[f"| {k} | {pct(v)} |" for k, v in summary["accuracy_by_category"].items()],
        "",
        "## By capability needed",
        "",
        "| Capability | Accuracy |",
        "|---|---|",
        *[f"| {k} | {pct(v)} |" for k, v in summary["accuracy_by_capability"].items()],
        "",
        "## Questions",
        "",
        "| Id | Category | Result | Score | Passages | Cited | Seconds |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in records:
        g = r["grading"]
        cited = "—" if not r["question"]["cite"] else ("yes" if g["citations"]["expected_cited"] else "no")
        passages = g["retrieval"].get("passages_hit")
        retrieved = "—" if passages is None else ("yes" if passages else "no")
        lines.append(
            f"| [{r['question']['id']}](answers/{r['question']['id']}.md){' (re-run)' if r.get('rerun') else ''} | {r['question']['category']} | "
            f"{'⚠️ not graded' if g.get('ungraded') else ('✅' if g['correct'] else '❌')} | {g['score']} | {retrieved} | {cited} | {r['timings'].get('answer_s')} |"
        )
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def latest_previous_run(runs_dir: Path, current: Path) -> dict | None:
    # Runs are named by start time; "previous" is the latest one started before this one.
    candidates = sorted(p for p in runs_dir.glob("*/run.json") if p.parent.name < current.name)
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))
