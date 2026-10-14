# Baseline evaluation · 14 October 2026

The first run of the DeepQuery evaluation set, recorded before any work on answer quality.
Every later run is compared against this one.

**Result: 5 of 33 questions answered correctly (15.2%), with a mean key-point score of 38.6%.**

## Setup

| | |
|---|---|
| Code | commit `c45850a` (`dev`) |
| Answering model | gpt-4o-mini (via gapgpt) |
| Grading model | gpt-5-mini (via gapgpt) |
| Embeddings | text-embedding-3-small; chunk size = the provider's 8,192-token limit |
| Retrieval | up to 15 chunks per question, ranked by vector similarity |
| Web search | **off in practice**: `SERPER_API_KEY` was a placeholder, so every search failed silently |
| Questions | 33 (30 English, 3 Persian) over 3 entity-linking papers, a spreadsheet, a CSV, 3 code files, notes in English and Persian, and 2 images |
| Duration | 16 minutes (8.3 s per answer on average) |

Each question ran in a fresh temporary chat: its files were uploaded and indexed, the question was
asked once, and the answer was graded on four things: the expected numbers, whether the right source
was retrieved and cited, and a grading model's check of each key point.

## Results

| Metric | Baseline |
|---|---|
| Correct answers | **5 / 33 (15.2%)** |
| Mean key-point score | 38.6% |
| Expected numbers present in the answer | 29.6% |
| Cited the source that holds the answer | 44.8% |
| Declined the 3 unanswerable questions | 0 / 3 |
| Retrieved the right source | 100% (not meaningful, see below) |

| Category | Correct |
|---|---|
| Facts from one paper (5) | 2 |
| Image (1) | 1 |
| Web (3) | 2 |
| Comparisons across papers (5) | 0 |
| Calculations from paper data (4) | 0 |
| Spreadsheet and CSV (6) | 0 |
| Code output (3) | 0 |
| Conflicting sources (1) | 0 |
| Unanswerable (3) | 0 |
| Persian (2) | 0 |

Correct: q01, q03 (single facts from one paper), q24 (speed ratios read from a table image),
q26 and q28 (web questions; see the caveat below).

## Why answers failed

The failures trace back to six causes. The first two are in how documents are ingested, not in
the model.

**1. The model received whole papers, with the spaces between words missing.**
The chunker sizes chunks by the embedding model's 8,192-token limit, so each 12-page paper
became just two chunks of about 20,000 characters, and every question's prompt contained the
entire paper (40,000–80,000 characters). The PDF extractor also drops the spaces inside
lines of these two-column papers. A typical passage the model saw:

> intensivebutcanbeparalleled. On8NvidiaVolta v100 GPUs, it takes about 2.8 hours

In almost every paper failure the right number *was* in the prompt; the model read the wrong
row or the wrong sentence. In q02 it attributed the 2.8 hours to the CPU server mentioned just
before; in q12 it produced numbers (75.01, 62.30) that appear nowhere in the paper.
Affected: q02, q04–q09, q12, q27, q29, q31.

**2. Only the first sheet of a spreadsheet is read.**
The GPU price sheet and the notes sheet ("exclude failed runs") of `reproduction_runs.xlsx`
never reached the model. In q16 it answered that it couldn't determine the cost.
Affected: q15, q16 (and the notes requirement in q14).

**3. The agent can't compute.**
Counting 240 CSV rows, summing a column or working out what a script prints all happen "in the
model's head". It computed 600 ÷ 120 as 15 days (q32), got a script's output wrong by a factor
of four (q23), and reported recall values that match neither the code nor the data (q22).
Affected: q17–q23, plus arithmetic slips in q10, q15 and q32.

**4. It answers instead of declining.**
For all three unanswerable questions it produced a confident answer: BLINK's 94.5 presented as
ReFinED's TACKBP-2010 score (q29), and an invented 54.00 for an empty cell in a table (q31).
q30 declined correctly but lost points to a grading rule that has since been fixed.

**5. Web search never ran.**
With a placeholder Serper key, no page was fetched for any web question. q26 and q28 were right
only because the model already knew the answers; q27 guessed the AIDA dataset size (2,882
documents instead of 1,393).

**6. A small answering model.**
gpt-4o-mini struggles to combine numbers from two papers (all 5 cross-paper questions failed)
and misread the lab notes in the conflict question (q25), concluding they agreed with the paper
when they didn't.

## Notes on the measurement

- **Graded by hand: q24, q25, q31.** The grading model failed on these: the two image questions
  crashed the grader (the provider rewrote the prompt it was given), and gpt-5-mini timed out on
  q31. Both bugs are fixed. The manual grades use the same key points; each file records the
  original error.
- **The retrieval score is not meaningful in this run.** With two chunks per paper, every chunk
  was always retrieved. Retrieval should be measured at passage level once chunks are smaller.
- **Two key points were stricter than their questions**: q30 (an optional detail counted as
  required) and q33 (asked for timings the question didn't ask for). They've been loosened for
  future runs. Under the fixed rules both would likely pass, giving about 7 / 33. The official
  baseline stays at 5 / 33, as graded.
- **The grader saw only the first 15,000 characters of each prompt's sources,** so it
  occasionally flagged a correct detail as unsupported (q30). Raised to 60,000 for later runs.

## What to fix first

In order of expected impact:

1. **Ingestion**: extract PDF text with correct spacing, chunk to a few hundred tokens with
   overlap, and read every sheet of a spreadsheet. This addresses causes 1 and 2 (about 13 questions).
2. **A computation tool** the agent can call for arithmetic, table statistics and running code
   (cause 3, about 10 questions).
3. **Declining when the sources don't say**, and a real Serper key for web search (causes 4 and 5).
4. **The answering model**: re-run with a stronger model to separate model limits from
   pipeline limits (cause 6).

## Files in this run

```
report.md              the generated summary and per-question table
run.json               the same numbers as JSON, with models, commit and timings
answers/<id>.md        each answer in full, next to the reference and the grading notes
questions/<id>.json    everything: extracted text, the full prompt, retrieved sources, raw grader reply
BASELINE.md            this document
```
