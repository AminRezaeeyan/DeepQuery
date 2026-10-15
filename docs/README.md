# DeepQuery technical documentation

How DeepQuery works, and why it's built the way it is.

| Page | Covers |
|---|---|
| [Architecture](architecture.md) | The system at a glance, data model, how a message flows, the streaming protocol, prompt budgets, memory, the provider registry, auth, plans |
| [The research agent](agent.md) | Why no framework, native tool calling, the loop and its phases (draft → critique → final), robustness, tools, citations, untrusted content |
| [Retrieval](retrieval.md) | Extraction per page and sheet, recursive chunking, embeddings, hybrid search (BM25 + reciprocal rank fusion), exact reading and matching, web sources |
| [Code execution](code-execution.md) | The `run_python` sandbox: bubblewrap namespaces, rlimits, modes, Docker, trade-offs |
| [The benchmark](evaluation.md) | Question design, how a run works, grading, scoring levels, re-runs, current results, the challenge |
| [Security](security.md) | Prompt injection, SSRF, ownership, authentication, secrets, uploads, known limits |
| [Deployment](deployment.md) | Docker Compose, local development, configuring models, every setting, CI |

## Reading order

New to the code? Read [Architecture](architecture.md) first, then [the agent](agent.md),
which is where most of the interesting decisions are. [The benchmark](evaluation.md) explains
how each decision was measured.

## Images

Screenshots used by the README live in [`images/`](images/).
