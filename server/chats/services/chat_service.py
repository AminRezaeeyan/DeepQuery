import json
import logging
import mimetypes

from django.db.models import Count
from chats.models import Chat, Message
from ai_core.exceptions import ContextLimitExceededError
from ai_core.services.chat_service import ChatGenerationService

logger = logging.getLogger(__name__)

# Answers stream as JSON lines, one event per line:
#   {"type": "text", "text": ...}       answer text
#   {"type": "reset"}                   drop the text so far (a preamble before tool calls)
#   {"type": "step", "id", "tool", "status": "running" | "done", "summary"}
#   {"type": "error", "detail": ...}    the answer failed after streaming started
STREAM_CONTENT_TYPE = "application/x-ndjson"


def event_line(event: dict) -> str:
    # Tool outputs stay on the server (they can be long and are for the model and the eval).
    public = {k: v for k, v in event.items() if k != "output"}
    return json.dumps(public, ensure_ascii=False) + "\n"


def stream_error(detail):
    return event_line({"type": "error", "detail": detail})


class ChatService:

    @staticmethod
    def get_or_create_chat(user, provider_id):
        chat = (
            Chat.objects
            .filter(user=user)
            .annotate(message_count=Count("messages"))
            .filter(message_count=0)
            .first()
        )

        if chat:
            return chat

        return Chat.objects.create(
            user=user,
            provider_id=provider_id,
        )
    
    @staticmethod
    def generate_stream(chat, user_message, enable_web_search=False, strict_quote_mode=False, audience_type="General", reasoning_depth="Medium", challenge_mode=False, on_incomplete=None):
 
        chat_service = ChatGenerationService(chat.user_id, chat.id, chat.provider_id, is_temporary=chat.is_temporary, enable_web_search=enable_web_search, strict_quote_mode=strict_quote_mode, audience_type=audience_type, reasoning_depth=reasoning_depth, challenge_mode=challenge_mode)
                
        image_bytes, mime_type = ChatService._read_image(user_message)

        # Raises before the response starts, so the view can return a 400.
        prepared = chat_service.prepare(user_message.content, history_before=user_message.created_at)

        def stream():
            assistant_text = ""
            steps = []
            completed = False

            try:
                for event in chat_service.answer_events(prepared, image_bytes=image_bytes, mime_type=mime_type):
                    if event["type"] == "text":
                        assistant_text += event["text"]
                    elif event["type"] == "reset":
                        assistant_text = ""
                    elif event["type"] == "step" and event["status"] == "done":
                        steps.append({"tool": event["tool"], "arguments": event["arguments"], "summary": event["summary"]})
                    yield event_line(event)

                Message.objects.create(
                    chat=chat,
                    role=Message.Role.ASSISTANT,
                    content=assistant_text,
                    trace=steps,
                )
                completed = True
            except ContextLimitExceededError as e:
                yield stream_error(str(e))
            except Exception:
                logger.exception("Answer stream failed for chat %s", chat.id)
                yield stream_error("The model stopped before finishing the answer. Try again.")
            finally:
                # Also runs on GeneratorExit, when the client disconnects.
                if not completed and on_incomplete:
                    on_incomplete()

        chat.mark_updated()
        return stream()
    
    @staticmethod
    def _read_image(message):
        if not message.image:
            return None, None
        mime_type = mimetypes.guess_type(message.image.name)[0]
        with message.image.open("rb") as f:
            return f.read(), mime_type

    @staticmethod
    def edit_user_message(old_message, new_content, on_incomplete=None, **answer_options):
        chat = old_message.chat

        # 1. Mark old user message deleted
        old_message.mark_edited()

        # 2. Soft delete assistant reply originally answering the old message
        assistant = (
            Message.objects
            .filter(
                chat=chat,
                role=Message.Role.ASSISTANT,
                created_at__gt=old_message.created_at
            )
            .order_by("created_at")
            .first()
        )

        if assistant:
            assistant.mark_deleted()

        # 3. Create new user message
        new_user_message = Message.objects.create(
            chat=chat,
            role=Message.Role.USER,
            content=new_content,
            image=old_message.image,
        )

        return ChatService.generate_stream(chat, new_user_message, on_incomplete=on_incomplete, **answer_options)
    
    @staticmethod
    def get_message_pairs(chat_id, cursor=None, limit=20):
        """
        Returns messages from newest → oldest.
        Cursor is the created_at of the last message from previous page.
        """

        qs = Message.objects.filter(chat_id=chat_id)

        if cursor:
            qs = qs.filter(created_at__lt=cursor)

        messages = list(
            qs.order_by("-created_at")
            .values("role", "content", "created_at")[:limit]
        )

        next_cursor = messages[-1]["created_at"] if messages else None

        result = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
        ]

        return result, next_cursor
