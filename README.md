<div align="center">
  <img src="docs/images/logo.svg" alt="DeepQuery Logo" width="400"/>

  <h1>DeepQuery</h1>
  <p><strong>An Advanced AI Research Assistant Agent</strong></p>

  [![Django](https://img.shields.io/badge/Django-6.0.3-092E20?style=flat-square&logo=django)](https://www.djangoproject.com/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
  [![Celery](https://img.shields.io/badge/Celery-5.6.3-37814A?style=flat-square&logo=celery)](https://docs.celeryq.dev/)
  [![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](#license)
</div>

## 📖 Overview

**DeepQuery** is an AI research assistant. You ask a question; it answers from the documents you upload, from web pages it searches for, and from what it remembers about you, and it cites the sources it used. It uses Retrieval-Augmented Generation (RAG) over PostgreSQL + pgvector and streams answers from the LLM provider you configure.

It's also a portfolio project, so the README describes what works today, not what's planned.

## ✨ Key Features

### 🧠 Research & RAG
*   **Document Q&A:** Upload PDF, TXT, Markdown, CSV, XLSX, JSON and code files to a chat. They're chunked, embedded and searched for every question in that chat.
*   **Web Search:** Optionally searches the web (via Serper), fetches the top pages and adds them to the chat's sources. URLs pasted into a question are fetched too, public addresses only.
*   **Citations:** The model is instructed to cite sources as `[1]`, `[2]`, and every answer ends with the list of sources that were retrieved for it. Whether each claim carries a citation depends on the model following that instruction.
*   **Conflicting Sources:** The model is instructed to point out when sources disagree ("Source [1] says X, but Source [2] says Y"). There's no separate conflict-detection step.
*   **Images:** Attach one image to a message when the selected model supports vision.
*   **Memory:** Recent chat history is included in each prompt. Personal facts you mention (in English or Persian) are extracted in the background and recalled in later chats when they're relevant.
*   **Token Budgets:** Each prompt section (sources, memory, history) gets a share of the model's context window, with room reserved for the answer and a safety margin.

### 🛠️ Answer Settings
Set per message in the composer:
*   **Temporary Chats:** For sensitive or one-off inquiries: the chat never reads or updates long-term memory and disappears from your history once you leave it.
*   **Strict Quote Mode:** Asks the model to back each major claim with a verbatim quote from the sources.
*   **Challenge Mode:** Asks the model to point out gaps, biases and missing perspectives in its own answer.
*   **Audience:** *General* or *Expert*.
*   **Depth:** Brief, balanced or deep answers (Low, Medium, High).

### ⚙️ Admin & Billing
Built with Django Jazzmin:
*   **Models:** Configure LLM providers (OpenAI and OpenAI-compatible APIs, Anthropic Claude, Google Gemini, Ollama) and embedding providers (OpenAI, Gemini, local Hugging Face models). API keys are encrypted in the database and never shown again after saving. Switching the active embedding provider re-embeds stored content in the background.
*   **Activity:** Browse chats, messages, documents and memory facts; restore deleted chats.
*   **Plans & Payments:** Daily limits per plan (messages, documents, images) and payments through ZarinPal.

### 🏗️ Architecture
*   **Django apps by domain:** users, chats, documents, ai_core (providers, RAG, memory, web search) and subscriptions.
*   **Provider registry:** New LLM or embedding providers register with a decorator; the factories need no changes.
*   **Background work:** Celery and Redis run document indexing, chat titles, memory extraction and re-embedding.
*   **Security:** JWT auth with token refresh, sign-in required by default, rate-limited sign-in, password validation, per-user data access, upload checks (ownership, size and file content), and retrieved text passed to the model as untrusted data.
*   **Tests:** About 180 server tests (pytest) and a client suite (Vitest), run by GitHub Actions on every push. The Claude, Gemini and Ollama providers are tested against mocked SDKs; the OpenAI-compatible provider has also been used against a live API.
*   **Web Client:** A React + TypeScript + Vite app in `client/` with dark and light themes (see `client/README.md`).

---

## 📸 Screenshots

*These show the earlier vanilla-JS client; the React client looks different.*


| Main Interface | Image Upload Usage |
| :---: | :---: |
| <img src="docs/images/main.png" width="400" alt="Main Chat Interface"/> | <img src="docs/images/image-upload.png" width="400" alt="Image Upload"/> |

| Source Conflict Detection | Admin Dashboard |
| :---: | :---: |
| <img src="docs/images/conflict.png" width="400" alt="Conflict Detection"/> | <img src="docs/images/admin-panel.png" width="400" alt="Jazzmin Admin Panel"/> |

---

## 💻 Tech Stack

**Server:**
*   Python 3.10+ (CI runs 3.12)
*   Django `6.0.3`, Django REST Framework `3.17.1`, SimpleJWT, drf-spectacular (Swagger/OpenAPI), Django Jazzmin
*   PostgreSQL + `pgvector`, Redis, Celery `5.6`
*   OpenAI, Anthropic and Google GenAI SDKs, sentence-transformers, tiktoken
*   pdfplumber, pandas, openpyxl, BeautifulSoup4

**Client:**
*   React, TypeScript, Vite, Vitest

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+ and Node.js 20+
*   PostgreSQL with the `pgvector` extension (on Ubuntu: `sudo apt install postgresql-16-pgvector`)
*   Redis

### 1. Server

```bash
git clone https://github.com/aminrezaeeyan/DeepQuery.git
cd DeepQuery/server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then edit: database, SERPER_API_KEY, ...
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver           # API on http://localhost:8000
```

> **Known issue:** chat currently fails to start an answer when `SERPER_API_KEY` is empty, even with web search off. Set it to any value if you don't need web search.

In a second terminal, from `server/`:

```bash
celery -A deepquery worker -l info
```

### 2. Configure models

Open the admin at http://localhost:8000/admin/ and add:
1. an **LLM provider** (for example OpenAI with your API key). The first one is used for every task: chat, titles, memory and search queries.
2. an **embedding provider** (for example OpenAI `text-embedding-3-small`, dimension 1536). The first one becomes active.

### 3. Client

```bash
cd client
npm install
npm run dev                          # http://localhost:5173
```

### Tests

```bash
cd server && pytest                  # needs PostgreSQL with pgvector
cd client && npm test
```
