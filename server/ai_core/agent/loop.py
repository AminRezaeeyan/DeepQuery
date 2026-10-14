"""
The research agent's loop, in plain Python: the model either answers or calls
tools; tool results go back into the conversation, and it goes again, up to a
step limit. Yields events for the stream:

    {"type": "step", "id", "tool", "status": "running" | "done", "summary", "output"?}
    {"type": "text", "text"}      answer text as it streams
    {"type": "reset"}             the text so far was a preamble before tool calls; drop it
"""
import json

from ai_core.services.token_service import TokenService

from .tools import ToolContext, describe_call, run_tool


def content_text(content) -> str:
    if isinstance(content, list):  # text plus an image
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def conversation_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += TokenService.count_tokens(content_text(m.get("content"))) + 4
        for call in m.get("tool_calls") or []:
            total += TokenService.count_tokens(call["function"]["arguments"])
    return total


class ResearchAgent:
    def __init__(self, provider, context: ToolContext, tools: list[dict], max_steps: int, token_budget: int, first_tool: str | None = None):
        self.provider = provider
        # A tool the first turn must call, e.g. search_documents when documents are attached:
        # small models otherwise skip the documents and guess or go straight to the web.
        self.first_tool = first_tool
        self.context = context
        self.tools = tools
        self.max_steps = max_steps
        self.token_budget = token_budget
        self.answer = ""

    def run(self, messages: list[dict]):
        """Runs the loop on `messages` (extended in place, so callers can record it)."""
        step_id = 0
        for turn in range(self.max_steps + 1):
            # Out of steps or room: the last turn must answer with what it has.
            final = turn == self.max_steps or conversation_tokens(messages) > self.token_budget
            choice = "none" if final else (self.first_tool if turn == 0 and self.first_tool else "auto")
            text, calls = "", None
            for kind, value in self.provider.stream_turn(messages, self.tools, tool_choice=choice):
                if kind == "text":
                    text += value
                    yield {"type": "text", "text": value}
                else:
                    calls = value

            if not calls:
                self.answer = text
                return

            if text:
                yield {"type": "reset"}
            messages.append({
                "role": "assistant",
                "content": text or None,
                "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
                    for c in calls
                ],
            })
            for call in calls:
                step_id += 1
                yield {"type": "step", "id": step_id, "tool": call.name, "arguments": call.arguments, "status": "running",
                       "summary": describe_call(call.name, call.arguments)}
                if call.error:
                    output_text, summary = call.error, f"{call.name}: invalid arguments"
                else:
                    output = run_tool(call.name, call.arguments, self.context)
                    output_text, summary = output.text, output.summary
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output_text})
                yield {"type": "step", "id": step_id, "tool": call.name, "arguments": call.arguments, "status": "done",
                       "summary": summary, "output": output_text}
