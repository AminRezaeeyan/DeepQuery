<div align="center">
  <img src="https://github.com/AminRezaeeyan/DeepQuery/blob/main/client/assets/images/logo.svg" alt="DeepQuery Logo" width="400"/>

  <p><strong>An Advanced AI Research Assistant Agent</strong></p>

  [![Django](https://img.shields.io/badge/Django-6.0.3-092E20?style=flat-square&logo=django)](https://www.djangoproject.com/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
  [![Celery](https://img.shields.io/badge/Celery-5.6.3-37814A?style=flat-square&logo=celery)](https://docs.celeryq.dev/)
  [![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](#license)
</div>

## 📖 Overview

**DeepQuery** is a professional-grade AI Research Assistant designed to process, analyze, and synthesize complex information from multiple sources. Utilizing Retrieval-Augmented Generation (RAG), it seamlessly handles multi-document uploads, web searches, and image processing while maintaining both short-term context and long-term memory. 

Engineered with token efficiency and safety in mind, DeepQuery doesn't just summarize—it critically analyzes data, detects conflicting information across sources, and provides precise citations for every claim.

## ✨ Key Features

### 🧠 Advanced AI & RAG Capabilities
*   **Intelligent Memory:** Utilizes both short-term conversational context and long-term memory retrieval.
*   **Multi-Modal Processing:** Supports concurrent analysis of multiple document formats (PDFs, Excel, etc.) and images.
*   **Web Search Integration:** Enhances localized knowledge with real-time web context.
*   **Conflict Detection:** Automatically cross-references multiple documents and flags conflicting information between sources.
*   **Precise Citations:** Every piece of synthesized knowledge is tracked back to its specific document or web source.
*   **Token Efficiency:** Highly optimized prompt engineering and a "safety buffer" mechanism prevent token waste and context window choking.

### 🛠️ Specialized Research Tools
DeepQuery offers granular control over the AI's behavior via specialized chat modes:
*   **Temporary Chats:** Disable long-term memory and storage for sensitive or one-off inquiries.
*   **Strict Quote Mode:** Forces the agent to answer using direct, verbatim quotes from documents/websites without altering the original context.
*   **Challenge Mode:** The AI critically analyzes its own synthesis to identify gaps, biases, or missing perspectives.
*   **Audience Targeting:** Toggle explanations between *General* or *Expert* levels.
*   **Reasoning Depth:** Adjust processing depth (Low, Medium, High) depending on whether you need a quick summary or a deep analytical breakdown.

### ⚙️ Powerful Admin
Built with Django Jazzmin, the admin panel provides complete operational control:
*   **LLM & Embedding Management:** Easily toggle and configure local models or API providers (OpenAI, Anthropic, Gemini, HuggingFace).
*   **User Activity:** Monitor chats, messages, and system usage.
*   **Subscription & Billing:** Manage subscription tiers, daily limits (messages, images, documents), and process payments via the Zarinpal SDK.

### 🏗️ Enterprise-Grade Architecture
*   **Clean & Decoupled:** Apps are heavily decoupled based on domain logic, ensuring near-zero coupling.
*   **Auto-Registry Factory Pattern:** Easily plug-and-play new LLMs or embedding providers without touching core logic.
*   **Asynchronous Processing:** Celery and Redis handle heavy embedding tasks and background jobs (like chat title generation) to keep the UI perfectly responsive.
*   **Robust Security:** Secured via JWT, CORS, and strict Django permission classes. Includes unit tests for mission-critical components.
*   **Test Client:** Includes a lightweight Vanilla JS frontend for easy API testing and demonstration.

---

## 📸 Screenshots


| Main Interface | Image Upload Usage |
| :---: | :---: |
| <img src="https://github.com/AminRezaeeyan/DeepQuery/blob/main/client/assets/images/main.png" width="500" alt="Main Chat Interface"/> | <img src="https://github.com/AminRezaeeyan/DeepQuery/blob/main/client/assets/images/image-upload.png" width="500" alt="Image Upload"/> |

| Source Conflict Detection | Admin Dashboard |
| :---: | :---: |
| <img src="https://github.com/AminRezaeeyan/DeepQuery/blob/main/client/assets/images/conflict.png" width="500" alt="Conflict Detection"/> | <img src="https://github.com/AminRezaeeyan/DeepQuery/blob/main/client/assets/images/admin-panel.png" width="500" alt="Jazzmin Admin Panel"/> |

---

## 💻 Tech Stack

**Core Framework & API:**
*   Python 3.x
*   Django `6.0.3` & Django REST Framework `3.17.1`
*   SimpleJWT, drf-spectacular (Swagger/OpenAPI)
*   Django-Jazzmin (Admin UI)

**Database & Task Queue:**
*   PostgreSQL + `pgvector` (Vector Search)
*   Redis `7.4` & Celery `5.6`

**AI & LLM Integration:**
*   OpenAI, Anthropic, Google GenAI, HuggingFace Hub
*   Tiktoken

**Data Processing:**
*   Pandas, Numpy, PDFPlumber, PyPDFium2
*   BeautifulSoup4, Openpyxl

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   PostgreSQL (with `pgvector` extension installed)
*   Redis Server

### Installation

1. **Clone the repository:**
```bash
   git clone https://github.com/aminrezaeeyan/DeepQuery.git
   cd DeepQuery/server
```
2. **Set up a virtual environment:**
```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
```
3. **Install dependencies:**
```bash
    pip install -r requirements.txt
```

4. **Environment Variables:**
Create a .env file in the root directory and add your configurations (Database credentials, API Keys, Redis URL, Zarinpal tokens, etc.).

5. **Database Setup:**
```python
       python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
```
6. **Run Background Workers (in a separate terminal):**
```python
      celery -A deepquery worker -l info
```
7. **Start the Development Server:**
```python
         python manage.py runserver
```

## 🛡️ Testing
Run the included test suite to verify core components:
```bash
pytest
```
## 🤝 Contributing
Contributions, issues, and feature requests are welcome!

## 📄 License
This project is licensed under the [MIT License](LICENSE).
