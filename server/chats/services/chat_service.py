import mimetypes

from django.db.models import Count
from chats.models import Chat, Message
from ai_core.exceptions import ProviderUnavailable
from ai_core.services.chat_service import ChatGenerationService


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
    def generate_stream(chat, user_message, enable_web_search=False, strict_quote_mode=False, audience_type="General", reasoning_depth="Medium", challenge_mode=False):
 
        try:
            chat_service = ChatGenerationService(chat.user_id, chat.id, chat.provider_id, is_temporary=chat.is_temporary, enable_web_search=enable_web_search, strict_quote_mode=strict_quote_mode, audience_type=audience_type, reasoning_depth=reasoning_depth, challenge_mode=challenge_mode)
        except ProviderUnavailable:
            raise
                
        image_bytes, mime_type = ChatService._read_image(user_message)

        def stream():
            assistant_text = ""

            for token in chat_service.stream_answer(
                user_message.content,
                image_bytes=image_bytes,
                mime_type=mime_type,
                history_before=user_message.created_at,
            ):
                assistant_text += token
                yield token

            Message.objects.create(
                chat=chat,
                role=Message.Role.ASSISTANT,
                content=assistant_text
            )

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
    def edit_user_message(old_message, new_content):
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
            content=new_content
        )

        return ChatService.generate_stream(chat, new_user_message)
    
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
