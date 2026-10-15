# Contributing to DeepQuery

Thanks for your interest! Bug reports, fixes, new tools, new providers, documentation and
benchmark results are all welcome.

## Ways to help

- **Beat the benchmark.** Our run with gpt-5-mini scored 31/33 on the [DeepQuery benchmark](docs/evaluation.md).
  The two misses are cross-paper comparisons over dense tables. Better table extraction,
  planning or a new tool could close the gap.
- **Add tool calling to another provider.** Claude, Gemini and Ollama answer in a single pass
  today; implementing `stream_turn` gives them the full agent
  ([agent.md](docs/agent.md#native-tool-calling)).
- **Improve retrieval**, e.g. a persistent BM25 index for large document sets
  ([retrieval.md](docs/retrieval.md)).
- **Report bugs** with steps to reproduce, and what you expected.

## Setting up

The quickest way is Docker ([deployment.md](docs/deployment.md)). For development you'll
usually run the server and client directly:

```bash
cd server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && pip install --no-deps -r requirements-nodeps.txt
cp .env.example .env
python manage.py migrate
cd ../client && npm install
```

You need PostgreSQL with pgvector and Redis running (or start just those with
`docker compose up -d db redis`).

## Before you open a pull request

```bash
cd server
pytest                                              # the full suite must pass
python manage.py makemigrations --check --dry-run   # no missing migrations
cd ../client
npm run typecheck && npm test && npm run build
```

- **Every bug fix comes with a test** that fails before the fix and passes after it.
- **Keep one pull request to one concern.**
- **Follow the code rules:**
  - no LangChain or agent frameworks;
  - every outgoing HTTP request has a timeout;
  - use `logging`, never `print`, and never log prompts, document text or keys;
  - untrusted content (documents, web pages, user input) is data, never instructions;
  - every query on user data is filtered by the requesting user;
  - Persian must keep working end to end.
- **Dependencies** are pinned in `requirements.txt`. Say why you need a new one.
- **Never edit an applied migration**; add a new one.

### Commit messages

`type(scope): description`, imperative and lowercase, 72 characters at most:

```
feat(ai_core): add a find_text tool for exact matches in documents
fix(providers): give reasoning turns a longer read timeout
docs(readme): document AGENT_REASONING_EFFORT
```

- **Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `style`, `chore`, `build`, `ci`.
- **Scopes:** `users`, `chats`, `documents`, `ai_core`, `providers`, `rag`, `memory`,
  `subscriptions`, `client`, `settings`, `deps`, `eval`, `readme`.

Add a body when the reason isn't obvious from the diff.

## Submitting a benchmark result

1. Run the full benchmark with a judge model at least as strong as the answering model:
   ```bash
   python manage.py run_eval --provider "<model>" --judge-provider "<judge>"
   ```
2. Put the run's `report.md` (and `run.json`) in your pull request description or as an
   attachment. Runs are not committed to the repository.
3. Say which models you used and whether any questions were re-run. The report lists re-runs
   automatically.

**What counts:** changes to the agent, its tools, retrieval or prompts that make it answer
better. **What doesn't count:**
- editing `eval/questions.yaml` or the sources to make questions easier;
- special-casing benchmark questions;
- using a judge weaker than the answering model.

If you find a genuine mistake in a reference answer, fix it in its own pull request and quote
the source that shows the reference is wrong.

## Questions

Open an issue. Describing what you're trying to do usually gets the most useful answer.
