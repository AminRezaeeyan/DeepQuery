# Evaluation run 20261014-110145-c45850a

- Commit: `c45850a`
- Agent model: gapgpt-gpt4o-mini (openai: gpt-4o-mini) · Judge model: gapgpt-gpt-5-mini (openai: gpt-5-mini) · Embeddings: gapgpt-text-embedding-3-small (text-embedding-3-small)
- Questions: 33 · Duration: 951.1 s
- Graded by hand: q24, q25, q31 (the judge call failed in this run; see BASELINE.md)

## Results

| Metric | Value |
|---|---|
| Accuracy | 15.2% |
| Mean key-point score | 38.6% |
| Expected numbers found | 29.6% |
| Retrieved the right source | 100.0% |
| Cited the right source | 44.8% |
| Declined unanswerable questions | 0.0% |

Correct: 5/33 · Answers citing a missing source: 0 · Errors: none · Not graded (judge failed): none

## By category

| Category | Accuracy |
|---|---|
| calculation | 0.0% |
| code | 0.0% |
| conflict | 0.0% |
| cross_paper | 0.0% |
| image | 100.0% |
| paper_fact | 40.0% |
| persian | 0.0% |
| spreadsheet | 0.0% |
| unanswerable | 0.0% |
| web | 66.7% |

## By capability needed

| Capability | Accuracy |
|---|---|
| abstention | 0.0% |
| code_reasoning | 0.0% |
| computation | 9.5% |
| conflict_detection | 0.0% |
| multi_doc | 0.0% |
| persian | 0.0% |
| retrieval | 12.5% |
| synthesis | 0.0% |
| table_reading | 0.0% |
| vision | 50.0% |
| web | 66.7% |

## Questions

| Id | Category | Result | Score | Retrieved | Cited | Seconds |
|---|---|---|---|---|---|---|
| [q01](answers/q01.md) | paper_fact | ✅ | 1.0 | yes | yes | 3.64 |
| [q02](answers/q02.md) | paper_fact | ❌ | 0.667 | yes | yes | 5.01 |
| [q03](answers/q03.md) | paper_fact | ✅ | 1.0 | yes | yes | 5.19 |
| [q04](answers/q04.md) | paper_fact | ❌ | 0.333 | yes | yes | 7.86 |
| [q05](answers/q05.md) | paper_fact | ❌ | 0.333 | yes | yes | 2.41 |
| [q06](answers/q06.md) | cross_paper | ❌ | 0.0 | yes | yes | 4.9 |
| [q07](answers/q07.md) | cross_paper | ❌ | 0.0 | yes | no | 5.81 |
| [q08](answers/q08.md) | cross_paper | ❌ | 0.0 | yes | yes | 5.73 |
| [q09](answers/q09.md) | cross_paper | ❌ | 0.667 | yes | yes | 7.57 |
| [q10](answers/q10.md) | calculation | ❌ | 0.333 | yes | no | 12.57 |
| [q11](answers/q11.md) | calculation | ❌ | 0.667 | yes | no | 20.08 |
| [q12](answers/q12.md) | calculation | ❌ | 0.0 | yes | yes | 25.58 |
| [q13](answers/q13.md) | calculation | ❌ | 0.667 | yes | no | 10.3 |
| [q14](answers/q14.md) | spreadsheet | ❌ | 0.5 | yes | no | 4.1 |
| [q15](answers/q15.md) | spreadsheet | ❌ | 0.333 | yes | no | 10.19 |
| [q16](answers/q16.md) | spreadsheet | ❌ | 0.333 | yes | no | 6.97 |
| [q17](answers/q17.md) | spreadsheet | ❌ | 0.0 | yes | no | 6.73 |
| [q18](answers/q18.md) | spreadsheet | ❌ | 0.0 | yes | no | 3.66 |
| [q19](answers/q19.md) | spreadsheet | ❌ | 0.5 | yes | yes | 5.2 |
| [q20](answers/q20.md) | cross_paper | ❌ | 0.0 | yes | yes | 6.43 |
| [q21](answers/q21.md) | code | ❌ | 0.25 | yes | no | 8.89 |
| [q22](answers/q22.md) | code | ❌ | 0.0 | yes | no | 7.84 |
| [q23](answers/q23.md) | code | ❌ | 0.0 | yes | no | 4.29 |
| [q24](answers/q24.md) | image | ✅ | 1.0 | — | — | 12.27 |
| [q25](answers/q25.md) | conflict | ❌ | 0.333 | yes | no | 8.98 |
| [q26](answers/q26.md) | web | ✅ | 1.0 | yes | no | 16.82 |
| [q27](answers/q27.md) | web | ❌ | 0.333 | yes | no | 9.35 |
| [q28](answers/q28.md) | web | ✅ | 1.0 | yes | no | 6.55 |
| [q29](answers/q29.md) | unanswerable | ❌ | 0.0 | — | — | 19.92 |
| [q30](answers/q30.md) | unanswerable | ❌ | 0.5 | — | — | 5.2 |
| [q31](answers/q31.md) | unanswerable | ❌ | 0.0 | — | — | 2.44 |
| [q32](answers/q32.md) | persian | ❌ | 0.5 | yes | yes | 7.35 |
| [q33](answers/q33.md) | persian | ❌ | 0.5 | yes | yes | 3.55 |
