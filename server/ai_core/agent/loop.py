"""
The research agent's loop, in plain Python: the model either answers or calls
tools; tool results go back into the conversation, and it goes again, up to a
step limit. Yields events for the stream:

    {"type": "step", "id", "tool", "status": "running" | "done", "summary", "output"?}
    {"type": "text", "text"}      answer text as it streams
    {"type": "reset"}             rare: streamed text turned out to be a preamble; drop it
"""
import json
import logging

from ai_core.exceptions import ProviderStalled
from ai_core.services.token_service import TokenService

from .prompts import REVIEW_REQUEST
from .tools import ToolContext, describe_call, run_tool

# A turn's text is held back until it's this long: models often write a short
# preamble ("Let me search the documents.") before calling tools, which isn't the answer.
PREAMBLE_CHARS = 200
# A turn whose stream stalls or drops is tried again once from the start.
TURN_ATTEMPTS = 2

logger = logging.getLogger(__name__)


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
    def __init__(self, provider, context: ToolContext, tools: list[dict], max_steps: int, token_budget: int,
                 first_tool: str | None = None, review: bool = False):
        self.provider = provider
        # A tool the first turn must call, e.g. search_documents when documents are attached:
        # small models otherwise skip the documents and guess or go straight to the web.
        self.first_tool = first_tool
        self.context = context
        self.tools = tools
        self.max_steps = max_steps
        self.token_budget = token_budget
        # Review: a draft answer that used tools is held back, and the model is asked to
        # check it against the tool results (and fix it, using tools if needed) once.
        self.review = review
        self.answer = ""
        self._pending = None  # a step event to send before the turn's first output

    def run(self, messages: list[dict]):
        """Runs the loop on `messages` (extended in place, so callers can record it)."""
        step_id, draft = 0, None
        for turn in range(self.max_steps + 1):
            # Out of steps or room: the last turn must answer with what it has.
            final = turn == self.max_steps or conversation_tokens(messages) > self.token_budget
            choice = "none" if final else (self.first_tool if turn == 0 and self.first_tool else "auto")
            hold = self.review and draft is None and step_id > 0 and not final
            for attempt in range(1, TURN_ATTEMPTS + 1):
                try:
                    text, calls, streaming = yield from self._turn(messages, choice, hold)
                    break
                except ProviderStalled:
                    if attempt == TURN_ATTEMPTS:
                        raise
                    logger.warning("The model's stream stalled; retrying the turn")
                    if self._streamed:
                        yield {"type": "reset"}  # drop the partial text before the retry streams

            if self._pending:  # the review turn produced tool calls and no text
                yield self._pending
                self._pending = None

            if not calls and hold and text:
                draft = text
                step_id += 1
                review = {"type": "step", "id": step_id, "tool": "check_answer", "arguments": {}, "summary": "Checking the answer"}
                yield {**review, "status": "running"}
                self._pending = {**review, "status": "done", "summary": "Checked the answer", "output": ""}
                messages.append({"role": "assistant", "content": draft})
                messages.append({"role": "user", "content": REVIEW_REQUEST})
                continue

            if not calls:
                if not text and draft:  # the review came back empty: keep the draft
                    text = draft
                if text and not streaming:
                    yield {"type": "text", "text": text}
                self.answer = text
                return

            if streaming:
                # Rare: a long text turned out to be a preamble after all.
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

    def _turn(self, messages, choice, hold=False):
        """Streams one model turn; returns (text, tool calls or None, whether text was streamed).

        With `hold`, nothing streams: the text is a draft for review.
        """
        text, calls, streaming = "", None, choice == "none" and not hold
        self._streamed = False
        for kind, value in self.provider.stream_turn(messages, self.tools, tool_choice=choice):
            if kind == "text":
                text += value
                if (streaming or (not hold and len(text) >= PREAMBLE_CHARS)) and self._pending:
                    yield self._pending
                    self._pending = None
                if streaming:
                    self._streamed = True
                    yield {"type": "text", "text": value}
                elif not hold and len(text) >= PREAMBLE_CHARS:
                    # Long enough to be the answer rather than "Let me check...": stream it.
                    streaming = self._streamed = True
                    yield {"type": "text", "text": text}
            else:
                calls = value
        return text, calls, streaming
