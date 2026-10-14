"""Instructions for the research agent, added to the shared answer rules."""
from documents.models import Document

AGENT_INSTRUCTIONS = """
HOW TO WORK: You are a research agent with tools. Work in steps: decide what you need, call a
tool, read the result, and repeat until you can answer, then answer.
- If documents are attached, always start with search_documents, even when the question asks you
  to search the web: it often depends on something only the documents say. Before quoting a number
  from a table, read that page or sheet with read_document so you copy it exactly.
- Use web_search, fetch_page and wikipedia (when available) for facts the documents don't have,
  or when the question asks you to look something up.
- Tool results show sources as [n] (source). Cite claims with those exact numbers.
- Don't repeat a search that already failed; rephrase it or try another tool.
- When the tools don't give you the answer, say so; don't fill the gap from memory.
- Your final message is the answer for the user; don't describe your process in it.
""".strip()


def chat_documents(chat_id: int, user_id: int):
    return Document.objects.filter(chat__id=chat_id, user_id=user_id, source_type=Document.SourceTypeChoices.FILE)


def has_documents(chat_id: int, user_id: int) -> bool:
    return chat_documents(chat_id, user_id).exists()


def documents_overview(chat_id: int, user_id: int) -> str:
    """Lists the attached documents and their parts, so the agent knows what it can read."""
    docs = chat_documents(chat_id, user_id)
    lines = []
    for doc in docs:
        labels = [s["label"] for s in doc.extracted_segments or [] if s.get("label")]
        if labels and labels[0].startswith("p. "):
            detail = f"{len(labels)} pages"
        elif labels:
            detail = "sheets: " + ", ".join(label.removeprefix("sheet: ") for label in labels)
        else:
            detail = "text"
        lines.append(f"- {doc.original_filename} ({detail}, {doc.status})")
    return "ATTACHED DOCUMENTS:\n" + "\n".join(lines) if lines else "No documents are attached to this chat."
